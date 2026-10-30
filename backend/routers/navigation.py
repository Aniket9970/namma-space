"""
routers/navigation.py — A* pathfinding and grid info routes.
"""

import json
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.scene import POI, Scene
from navigation.astar import astar
from navigation.grid_utils import grid_to_world, world_to_grid

router = APIRouter()

STATIC_ROOT = Path("static")


def _load_grid_and_meta(scene: Scene) -> tuple[np.ndarray, dict]:
    """Load occupancy grid and metadata for a scene."""
    if not scene.grid_meta_json:
        raise HTTPException(status_code=422, detail="Scene has no grid metadata. Run build_occupancy_grid.py first.")

    meta = json.loads(scene.grid_meta_json)

    # Resolve grid path
    grid_path_str = scene.grid_path or "static/navigation/grid.npy"
    grid_path = Path(grid_path_str.lstrip("/"))
    if not grid_path.exists():
        # Try relative to static
        grid_path = STATIC_ROOT / "navigation" / "grid.npy"

    if not grid_path.exists():
        raise HTTPException(status_code=404, detail=f"Occupancy grid file not found: {grid_path}")

    grid = np.load(str(grid_path))
    return grid, meta


@router.get("/scenes/{scene_id}/grid")
async def get_grid_metadata(scene_id: int, db: AsyncSession = Depends(get_db)):
    """Return occupancy grid metadata (origin, cell size, dimensions)."""
    scene = await db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    if not scene.grid_meta_json:
        raise HTTPException(status_code=404, detail="No grid metadata for this scene")

    return json.loads(scene.grid_meta_json)


@router.get("/scenes/{scene_id}/path")
async def get_path(
    scene_id: int,
    from_poi: int = Query(..., description="Source POI id"),
    to_poi: int = Query(..., description="Destination POI id"),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute A* path from source POI to destination POI.
    Returns {"path": [[x, y, z], ...]} in world coordinates.
    """
    scene = await db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    src_poi = await db.get(POI, from_poi)
    dst_poi = await db.get(POI, to_poi)

    if not src_poi or src_poi.scene_id != scene_id:
        raise HTTPException(status_code=404, detail=f"Source POI {from_poi} not found in scene")
    if not dst_poi or dst_poi.scene_id != scene_id:
        raise HTTPException(status_code=404, detail=f"Destination POI {to_poi} not found in scene")

    grid, meta = _load_grid_and_meta(scene)

    origin = tuple(meta["origin"])
    cell_size = meta["cell_size"]
    floor_y = meta.get("floor_y", 0.0)
    rows = meta["rows"]
    cols = meta["cols"]

    def clamp_cell(col: int, row: int) -> tuple[int, int]:
        return (max(0, min(cols - 1, col)), max(0, min(rows - 1, row)))

    # Convert world → grid
    src_col, src_row = world_to_grid(src_poi.x, src_poi.z, origin, cell_size)
    dst_col, dst_row = world_to_grid(dst_poi.x, dst_poi.z, origin, cell_size)
    src_col, src_row = clamp_cell(src_col, src_row)
    dst_col, dst_row = clamp_cell(dst_col, dst_row)

    # Run A*
    path_cells = astar(grid, (src_row, src_col), (dst_row, dst_col))

    if not path_cells:
        raise HTTPException(status_code=422, detail="No path found between the selected POIs")

    # Convert grid path → world 3D coordinates
    path_world = []
    for row, col in path_cells:
        wx, wz = grid_to_world(row, col, origin, cell_size)
        path_world.append([wx, floor_y + 0.05, wz])  # slightly above floor

    return {"path": path_world, "cell_count": len(path_cells)}
