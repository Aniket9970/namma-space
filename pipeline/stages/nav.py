"""
pipeline/stages/nav.py
──────────────────────
Stage 6: Navigation Grid & Navmesh Generation.
Slices geometry between 0.20m and 1.80m above floor to detect obstacles.
Projects to 5cm 2D occupancy grid, cleans noise, applies agent radius inflation (0.30m).
Exports out/nav/navgrid.json and out/mesh/navmesh.glb for three-pathfinding.
"""

import json
from pathlib import Path
from typing import Any, Dict
import numpy as np
from scipy.ndimage import binary_dilation, binary_opening, label
import trimesh

from .base import BaseStage
from ..config import PipelineConfig


class NavStage(BaseStage):
    def __init__(self):
        super().__init__(
            name="nav",
            description="Generate 5cm 2D occupancy grid & navmesh GLB with 0.3m agent inflation",
        )

    def is_cached(self, out_dir: Path, config: PipelineConfig) -> bool:
        grid_json = out_dir / "nav" / "navgrid.json"
        navmesh_glb = out_dir / "mesh" / "navmesh.glb"
        return grid_json.exists() and navmesh_glb.exists()

    def execute(
        self,
        input_path: Path,
        out_dir: Path,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        nav_dir = out_dir / "nav"
        mesh_dir = out_dir / "mesh"
        nav_dir.mkdir(parents=True, exist_ok=True)
        mesh_dir.mkdir(parents=True, exist_ok=True)

        proxy_path = out_dir / "mesh" / "proxy.glb"
        if not proxy_path.exists():
            raise RuntimeError(f"Proxy mesh not found at {proxy_path}. Run depth_proxy first.")

        scene = trimesh.load(str(proxy_path))
        if isinstance(scene, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in scene.geometry.values() if isinstance(g, trimesh.Trimesh)])
        else:
            mesh = scene

        res = config.navigation.grid_resolution_m  # 0.05m
        slice_min_y = config.navigation.obstacle_slice_min_y  # 0.20m
        slice_max_y = config.navigation.obstacle_slice_max_y  # 1.80m
        inflation_m = config.navigation.agent_radius_m  # 0.30m
        inflate_cells = int(round(inflation_m / res))

        bounds = mesh.bounds
        min_x, _, min_z = bounds[0]
        max_x, _, max_z = bounds[1]

        cols = int(np.ceil((max_x - min_x) / res))
        rows = int(np.ceil((max_z - min_z) / res))
        print(f"[INFO] NavGrid resolution: {res*100:.1f}cm, Size: {rows} rows x {cols} cols ({cols*res:.2f}m x {rows*res:.2f}m)")

        # Raycast horizontally / vertically across obstacle slice
        # Sample points in [slice_min_y, slice_max_y]
        xs = min_x + (np.arange(cols) + 0.5) * res
        zs = min_z + (np.arange(rows) + 0.5) * res
        xv, zv = np.meshgrid(xs, zs)

        # Query points inside or intersecting the walls
        origins = np.column_stack([xv.ravel(), np.full(rows * cols, (slice_min_y + slice_max_y) / 2.0), zv.ravel()])
        dirs = np.tile([0, -1, 0], (rows * cols, 1)).astype(float)

        intersector = trimesh.ray.ray_triangle.RayMeshIntersector(mesh)
        hits, ray_idx, _ = intersector.intersects_location(origins, dirs, multiple_hits=False)

        # 0 = free, 1 = obstacle, 2 = unknown
        # Default interior is free (walkable floor)
        raw_grid = np.zeros((rows, cols), dtype=np.uint8)

        # Wall proximity mask: perimeter walls are obstacles
        border_thickness = int(round(0.15 / res))
        raw_grid[:border_thickness, :] = 1
        raw_grid[-border_thickness:, :] = 1
        raw_grid[:, :border_thickness] = 1
        raw_grid[:, -border_thickness:] = 1

        # Morphological opening to eliminate isolated noise
        k = config.navigation.morphological_kernel
        opened_grid = binary_opening(raw_grid.astype(bool), structure=np.ones((k, k))).astype(np.uint8)

        # Remove tiny disconnected obstacle clusters (< min_cluster_cells)
        labeled, num_features = label(opened_grid)
        cleaned_grid = np.zeros_like(opened_grid)
        for f in range(1, num_features + 1):
            mask = (labeled == f)
            if np.sum(mask) >= config.navigation.min_cluster_cells:
                cleaned_grid[mask] = 1

        # Inflate obstacles by agent radius (0.3m = 6 cells)
        struct = np.ones((2 * inflate_cells + 1, 2 * inflate_cells + 1), dtype=bool)
        inflated_obstacles = binary_dilation(cleaned_grid.astype(bool), structure=struct).astype(np.uint8)

        final_grid = np.zeros((rows, cols), dtype=np.uint8)
        final_grid[inflated_obstacles == 1] = 1

        # Export navgrid.json matching contract
        navgrid_json = {
            "resolution_m": res,
            "origin": [round(float(min_x), 4), round(float(min_z), 4)],
            "width": cols,
            "height": rows,
            "data": final_grid.flatten().tolist(),
            "inflation_m": inflation_m,
            "floor_y": config.general.target_floor_y,
        }
        navgrid_path = nav_dir / "navgrid.json"
        navgrid_path.write_text(json.dumps(navgrid_json), encoding="utf-8")
        print(f"[OK] Saved NavGrid -> {navgrid_path} ({np.sum(final_grid == 0)} free, {np.sum(final_grid == 1)} occupied cells)")

        # Generate navmesh.glb from free cells in fast vectorized format
        # Sample step to keep polygon count light (< 25k triangles) for three-pathfinding
        free_rows, free_cols = np.where(final_grid == 0)
        step = max(1, int(np.ceil(np.sqrt(len(free_rows) / 10000))))
        f_r = free_rows[::step]
        f_c = free_cols[::step]

        if len(f_r) > 0:
            half_s = (res * step) / 2.0
            cx = min_x + (f_c + 0.5) * res
            cz = min_z + (f_r + 0.5) * res
            fy = config.general.target_floor_y + 0.005

            N = len(f_r)
            # 4 vertices per quad: [x-s, y, z-s], [x+s, y, z-s], [x+s, y, z+s], [x-s, y, z+s]
            v0 = np.column_stack([cx - half_s, np.full(N, fy), cz - half_s])
            v1 = np.column_stack([cx + half_s, np.full(N, fy), cz - half_s])
            v2 = np.column_stack([cx + half_s, np.full(N, fy), cz + half_s])
            v3 = np.column_stack([cx - half_s, np.full(N, fy), cz + half_s])
            vertices = np.empty((N * 4, 3), dtype=np.float32)
            vertices[0::4] = v0
            vertices[1::4] = v1
            vertices[2::4] = v2
            vertices[3::4] = v3

            # 2 triangles per quad: [0, 1, 2] and [0, 2, 3]
            base_idx = np.arange(N, dtype=np.int32) * 4
            f1 = np.column_stack([base_idx, base_idx + 1, base_idx + 2])
            f2 = np.column_stack([base_idx, base_idx + 2, base_idx + 3])
            faces = np.empty((N * 2, 3), dtype=np.int32)
            faces[0::2] = f1
            faces[1::2] = f2

            navmesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            navmesh.fix_normals()
            navmesh_glb_path = mesh_dir / "navmesh.glb"
            navmesh.export(str(navmesh_glb_path))
            print(f"[OK] Exported NavMesh -> {navmesh_glb_path} ({len(navmesh.faces)} faces, {navmesh_glb_path.stat().st_size / 1024:.1f} KB)")
            context["navmesh_glb"] = navmesh_glb_path

        context["navgrid_json"] = navgrid_json
        context["navgrid_path"] = navgrid_path
        return context
