1#!/usr/bin/env python3
"""
build_occupancy_grid.py
─────────────────────────────────────────────────────────────────────────────
Build a 2D binary occupancy grid from a .glb mesh for use by the A* pathfinder.

Algorithm:
  1. Load the GLB with trimesh.
  2. Determine the XZ bounding box of the mesh.
  3. Sample a regular grid of points at floor_height + sample_z (slightly above floor).
  4. For each grid cell, cast a ray straight down; if it hits geometry within
     max_hit_dist metres, mark the cell occupied.
  5. Inflate obstacles by inflate_cells to account for agent radius.
  6. Save grid as uint8 numpy array (0=free, 1=occupied) + JSON metadata.
  7. Copy both files to ../backend/static/navigation/.

Usage:
    python build_occupancy_grid.py [--glb ../backend/static/models/scene.glb]
                                   [--cell-size 0.1]
                                   [--floor-height 0.0]
                                   [--inflate 2]
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np

try:
    import trimesh
    import trimesh.ray
except ImportError:
    print("[ERROR] trimesh not installed. Run: pip install trimesh", file=sys.stderr)
    sys.exit(1)


def inflate_grid(grid: np.ndarray, cells: int) -> np.ndarray:
    """Binary dilation — inflate occupied cells by `cells` in all 8 directions."""
    if cells <= 0:
        return grid
    from scipy.ndimage import binary_dilation
    struct = np.ones((2 * cells + 1, 2 * cells + 1), dtype=bool)
    return binary_dilation(grid.astype(bool), structure=struct).astype(np.uint8)


def build_grid(
    glb_path: Path,
    cell_size: float = 0.1,
    floor_height: float = 0.0,
    sample_z: float = 0.1,
    max_hit_dist: float = 2.0,
    inflate_cells: int = 2,
) -> tuple[np.ndarray, dict]:
    print(f"[INFO] Loading mesh: {glb_path}")
    scene = trimesh.load(str(glb_path))

    # Flatten scene to a single mesh
    if isinstance(scene, trimesh.Scene):
        meshes = [g for g in scene.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            print("[ERROR] No Trimesh geometry found in the GLB.", file=sys.stderr)
            sys.exit(1)
        mesh = trimesh.util.concatenate(meshes)
    elif isinstance(scene, trimesh.Trimesh):
        mesh = scene
    else:
        print(f"[ERROR] Unexpected mesh type: {type(scene)}", file=sys.stderr)
        sys.exit(1)

    bounds = mesh.bounds  # [[min_x, min_y, min_z], [max_x, max_y, max_z]]
    min_x, _, min_z = bounds[0]
    max_x, _, max_z = bounds[1]

    print(f"[INFO] Mesh bounds XZ: ({min_x:.2f}, {min_z:.2f}) -> ({max_x:.2f}, {max_z:.2f})")

    # Grid dimensions
    cols = int(np.ceil((max_x - min_x) / cell_size))
    rows = int(np.ceil((max_z - min_z) / cell_size))
    print(f"[INFO] Grid size: {rows} rows x {cols} cols  (cell={cell_size}m)")

    # Build ray origins — one per cell, shot downward
    ray_height = floor_height + sample_z
    xs = min_x + (np.arange(cols) + 0.5) * cell_size
    zs = min_z + (np.arange(rows) + 0.5) * cell_size
    xv, zv = np.meshgrid(xs, zs)  # shape (rows, cols)

    origins = np.column_stack([
        xv.ravel(),
        np.full(rows * cols, ray_height),
        zv.ravel(),
    ])
    directions = np.tile([0, -1, 0], (rows * cols, 1)).astype(float)

    print("[INFO] Raycasting...")
    ray_intersector = trimesh.ray.ray_triangle.RayMeshIntersector(mesh)
    hit_locations, index_ray, _ = ray_intersector.intersects_location(
        origins, directions, multiple_hits=False
    )

    grid = np.zeros((rows, cols), dtype=np.uint8)

    if len(hit_locations) > 0:
        hit_y = hit_locations[:, 1]
        hit_rows = index_ray // cols
        hit_cols = index_ray % cols
        dist_below = ray_height - hit_y
        valid = dist_below <= max_hit_dist
        grid[hit_rows[valid], hit_cols[valid]] = 1

    # Invert: occupied = cells where mesh was hit (i.e., solid geometry)
    # Free = cells where ray didn't hit anything (open air above floor)
    # For navigation, we want occupied = walls/obstacles, free = walkable floor.
    # Swap: hit = obstacle, no-hit = open floor
    occupied = grid.copy()
    grid_nav = np.ones((rows, cols), dtype=np.uint8)  # start all occupied
    grid_nav[occupied == 1] = 0  # mark floor cells as free

    # Inflate obstacles
    print(f"[INFO] Inflating obstacles by {inflate_cells} cells...")
    grid_nav = inflate_grid(grid_nav, inflate_cells)

    meta = {
        "origin": [float(min_x), float(min_z)],
        "cell_size": cell_size,
        "rows": rows,
        "cols": cols,
        "floor_y": floor_height,
    }

    occupied_count = int(np.sum(grid_nav))
    free_count = int(rows * cols) - occupied_count
    print(f"[INFO] Grid: {free_count} free cells, {occupied_count} occupied cells")

    return grid_nav, meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 2D occupancy grid from a GLB mesh.")
    parser.add_argument("--glb", default="../backend/static/models/scene.glb")
    parser.add_argument("--cell-size", type=float, default=0.1)
    parser.add_argument("--floor-height", type=float, default=0.0)
    parser.add_argument("--inflate", type=int, default=2)
    parser.add_argument("--backend", default="../backend")
    args = parser.parse_args()

    glb_path = Path(args.glb)
    if not glb_path.exists():
        print(f"[ERROR] GLB not found: {glb_path}", file=sys.stderr)
        sys.exit(1)

    grid, meta = build_grid(
        glb_path,
        cell_size=args.cell_size,
        floor_height=args.floor_height,
        inflate_cells=args.inflate,
    )

    # Save locally
    out_dir = Path("output/navigation")
    out_dir.mkdir(parents=True, exist_ok=True)
    grid_path = out_dir / "grid.npy"
    meta_path = out_dir / "occupancy_meta.json"
    np.save(str(grid_path), grid)
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"[OK] Grid -> {grid_path}")
    print(f"[OK] Meta -> {meta_path}")

    # Copy to backend
    backend_nav = Path(args.backend) / "static" / "navigation"
    backend_nav.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(grid_path), str(backend_nav / "grid.npy"))
    shutil.copy2(str(meta_path), str(backend_nav / "occupancy_meta.json"))
    print(f"[OK] Copied to {backend_nav}/")

    print("\n[DONE] Occupancy grid build complete.")


if __name__ == "__main__":
    main()
