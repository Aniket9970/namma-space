"""
pipeline/stages/nav.py
──────────────────────
Stage 6: Navigation Grid & Navmesh Generation.
Slices geometry between 0.20m and 1.80m above floor to detect true obstacles.
Projects to 5cm 2D occupancy grid:
  0 = Free / Walkable
  1 = Obstacle
  2 = Unknown / Unobserved
Cleans noise with morphological opening and connected components.
Applies configurable agent radius inflation (default 0.30m).
Exports out/nav/navgrid.json and out/mesh/navmesh.glb for three-pathfinding.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import cv2
import numpy as np
from scipy.ndimage import binary_dilation, binary_opening, label
import trimesh

from .base import BaseStage
from ..config import PipelineConfig


class NavStage(BaseStage):
    """
    Milestone M5: Navigation Grid & Navmesh Generation.
    """

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

        res = config.navigation.grid_resolution_m  # 0.05m (5 cm)
        slice_min_y = config.navigation.obstacle_slice_min_y  # 0.20m
        slice_max_y = config.navigation.obstacle_slice_max_y  # 1.80m
        inflation_m = config.navigation.agent_radius_m  # 0.30m
        inflate_cells = int(round(inflation_m / res))

        # Determine 2D floorplan bounding box with padding
        bounds = mesh.bounds
        min_x = float(bounds[0][0] - 0.4)
        max_x = float(bounds[1][0] + 0.4)
        min_z = float(bounds[0][2] - 0.4)
        max_z = float(bounds[1][2] + 0.4)

        cols = int(np.ceil((max_x - min_x) / res))
        rows = int(np.ceil((max_z - min_z) / res))
        print(f"[INFO] NavGrid resolution: {res*100:.1f}cm, Size: {cols}x{rows} ({cols*res:.2f}m x {rows*res:.2f}m)")

        # 1. Initialize grid: 2 = Unknown, 0 = Free, 1 = Obstacle
        grid = np.full((rows, cols), 2, dtype=np.uint8)

        # Mark floor footprint from proxy mesh floor vertices as observed
        verts = mesh.vertices
        floor_verts = verts[verts[:, 1] < 0.25]
        if len(floor_verts) > 10:
            # Convex hull of floor in 2D
            pts_2d = floor_verts[:, [0, 2]]
            c_floor = np.clip(np.floor((pts_2d[:, 0] - min_x) / res).astype(np.int32), 0, cols - 1)
            r_floor = np.clip(np.floor((pts_2d[:, 1] - min_z) / res).astype(np.int32), 0, rows - 1)
            hull_pts = cv2.convexHull(np.column_stack([c_floor, r_floor]))
            cv2.fillPoly(grid, [hull_pts], 0)
        else:
            # Fallback interior box
            border = int(round(0.4 / res))
            grid[border:-border, border:-border] = 0

        # 2. Slice 3D mesh triangles in height window [slice_min_y, slice_max_y]
        tri_centers = np.mean(mesh.vertices[mesh.faces], axis=1)
        obstacle_faces = mesh.faces[(tri_centers[:, 1] >= slice_min_y) & (tri_centers[:, 1] <= slice_max_y)]

        if len(obstacle_faces) > 0:
            obs_verts = mesh.vertices[obstacle_faces.ravel()]
            # Rasterize obstacle vertices and edges onto grid
            obs_cols = np.clip(np.floor((obs_verts[:, 0] - min_x) / res).astype(int), 0, cols - 1)
            obs_rows = np.clip(np.floor((obs_verts[:, 2] - min_z) / res).astype(int), 0, rows - 1)
            grid[obs_rows, obs_cols] = 1

        # Also slice sparse points if available
        aligned_poses_path = out_dir / "aligned_poses.json"
        if aligned_poses_path.exists():
            try:
                p_data = json.loads(aligned_poses_path.read_text(encoding="utf-8"))
                sparse_pts = np.array([p["xyz"] for p in p_data.get("sparse_points", [])])
                if len(sparse_pts) > 0:
                    obs_sparse = sparse_pts[(sparse_pts[:, 1] >= slice_min_y) & (sparse_pts[:, 1] <= slice_max_y)]
                    if len(obs_sparse) > 0:
                        s_c = np.clip(np.floor((obs_sparse[:, 0] - min_x) / res).astype(int), 0, cols - 1)
                        s_r = np.clip(np.floor((obs_sparse[:, 2] - min_z) / res).astype(int), 0, rows - 1)
                        grid[s_r, s_c] = 1
            except Exception:
                pass

        # 3. Clean noise with morphological opening
        raw_obstacles = (grid == 1)
        k = config.navigation.morphological_kernel
        opened_obstacles = binary_opening(raw_obstacles, structure=np.ones((k, k)))

        # Remove tiny isolated clusters (< min_cluster_cells)
        labeled, num_features = label(opened_obstacles)
        cleaned_obstacles = np.zeros_like(opened_obstacles, dtype=bool)
        for f in range(1, num_features + 1):
            mask = (labeled == f)
            if np.sum(mask) >= config.navigation.min_cluster_cells:
                cleaned_obstacles[mask] = True

        # 4. Inflate obstacles by agent radius (0.3m)
        struct = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * inflate_cells + 1, 2 * inflate_cells + 1)).astype(bool)
        inflated_obstacles = binary_dilation(cleaned_obstacles, structure=struct)

        # Assemble final grid:
        # Unknown regions stay 2 (do NOT inflate unknown regions into the room)
        final_grid = np.copy(grid)
        # Apply cleaned & inflated obstacles
        final_grid[inflated_obstacles] = 1

        free_count = int(np.sum(final_grid == 0))
        obs_count = int(np.sum(final_grid == 1))
        unk_count = int(np.sum(final_grid == 2))
        print(f"[INFO] NavGrid cells: {free_count} Free, {obs_count} Obstacle (inflated {inflation_m}m), {unk_count} Unknown")

        # 5. Export navgrid.json
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
        print(f"[OK] Saved NavGrid -> {navgrid_path}")

        # 6. Generate vectorized navmesh.glb from walkable free cells for three-pathfinding
        free_rows, free_cols = np.where(final_grid == 0)
        # Target ~10k to 20k triangles for smooth 60fps in Three.js
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

            # 2 triangles per quad
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
