"""
routers/navigation.py — A* pathfinding and grid info routes.
Supports both legacy grid.npy and modern navgrid.json contracts.
"""

import json
from pathlib import Path
import sys
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.scene import POI, Scene
from navigation.astar import astar as legacy_astar
from navigation.grid_utils import grid_to_world as legacy_g2w, world_to_grid as legacy_w2g

# Import M5 reference planner if available
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from nav.plan import NavGrid, plan_path_astar, smooth_path
    HAS_NAV_PLAN = True
except ImportError:
    HAS_NAV_PLAN = False

router = APIRouter()
STATIC_ROOT = Path("static")


class RouteRequest(BaseModel):
    start: List[float]  # [x, y, z]
    goal: List[float]   # [x, y, z]


def _find_navgrid_json(scene: Scene) -> Optional[Path]:
    """Find navgrid.json for a given scene."""
    if scene.tour_path:
        tour_file = Path(scene.tour_path.lstrip("/"))
        if tour_file.exists():
            try:
                data = json.loads(tour_file.read_text(encoding="utf-8"))
                navgrid_rel = data.get("navgrid", "nav/navgrid.json")
                cand = tour_file.parent / navgrid_rel
                if cand.exists():
                    return cand
            except Exception:
                pass

    candidates = [
        STATIC_ROOT / "navigation" / "navgrid.json",
        STATIC_ROOT / "panoramas" / "sample_scene" / "nav" / "navgrid.json",
        STATIC_ROOT / "panoramas" / "sample_scene" / "navgrid.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


@router.get("/scenes/{scene_id}/grid")
async def get_grid_metadata(scene_id: int, db: AsyncSession = Depends(get_db)):
    """Return occupancy grid metadata."""
    scene = await db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    navgrid_path = _find_navgrid_json(scene)
    if navgrid_path:
        return json.loads(navgrid_path.read_text(encoding="utf-8"))

    if scene.grid_meta_json:
        return json.loads(scene.grid_meta_json)

    raise HTTPException(status_code=404, detail="No navigation grid metadata for this scene")


@router.post("/scenes/{scene_id}/route")
async def plan_route_between_coordinates(
    scene_id: int,
    req: RouteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Compute obstacle-aware walking path between arbitrary world coordinates [x, y, z].
    """
    scene = await db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    navgrid_path = _find_navgrid_json(scene)
    if navgrid_path and HAS_NAV_PLAN:
        nav = NavGrid.from_json(navgrid_path)
        start_xz = (req.start[0], req.start[2] if len(req.start) > 2 else req.start[1])
        goal_xz = (req.goal[0], req.goal[2] if len(req.goal) > 2 else req.goal[1])

        raw_path = plan_path_astar(nav, start_xz, goal_xz)
        if not raw_path:
            raise HTTPException(status_code=422, detail="No obstacle-free path found")

        smoothed = smooth_path(nav, raw_path)
        path_3d = [[round(p[0], 3), round(nav.floor_y + 0.05, 3), round(p[1], 3)] for p in smoothed]

        # Calculate distance
        dist = 0.0
        for i in range(len(path_3d) - 1):
            p1, p2 = np.array(path_3d[i]), np.array(path_3d[i + 1])
            dist += float(np.linalg.norm(p2 - p1))

        return {
            "path": path_3d,
            "waypoint_count": len(path_3d),
            "distance_m": round(dist, 2),
            "eta_sec": int(round(dist / 1.2)),
        }

    # Fallback to POI path if navgrid.json is missing
    raise HTTPException(status_code=422, detail="Navigation grid not ready for this scene.")


@router.get("/scenes/{scene_id}/path")
async def get_path(
    scene_id: int,
    from_poi: int = Query(..., description="Source POI id"),
    to_poi: int = Query(..., description="Destination POI id"),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute A* path from source POI to destination POI.
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

    navgrid_path = _find_navgrid_json(scene)
    if navgrid_path and HAS_NAV_PLAN:
        nav = NavGrid.from_json(navgrid_path)
        start_xz = (src_poi.x, src_poi.z)
        goal_xz = (dst_poi.x, dst_poi.z)

        raw_path = plan_path_astar(nav, start_xz, goal_xz)
        if not raw_path:
            raise HTTPException(status_code=422, detail="No obstacle-free path found between POIs")

        smoothed = smooth_path(nav, raw_path)
        path_3d = [[round(p[0], 3), round(nav.floor_y + 0.05, 3), round(p[1], 3)] for p in smoothed]
        return {"path": path_3d, "cell_count": len(path_3d)}

    raise HTTPException(status_code=422, detail="Navigation grid not found.")
