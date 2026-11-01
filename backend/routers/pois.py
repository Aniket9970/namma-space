"""
routers/pois.py — POI CRUD + fuzzy search routes.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fuzzywuzzy import process as fw_process
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.scene import POI, Scene
from navigation.grid_utils import world_to_grid

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class POICreate(BaseModel):
    name: str
    description: str | None = None
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class POIUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None


class POIResponse(BaseModel):
    id: int
    scene_id: int
    name: str
    description: str | None
    x: float
    y: float
    z: float
    grid_col: int | None
    grid_row: int | None

    model_config = {"from_attributes": True}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _compute_grid_cell(scene: Scene, x: float, z: float) -> tuple[int | None, int | None]:
    """Convert world coordinates to grid row/col using scene metadata."""
    if not scene.grid_meta_json:
        return None, None
    try:
        meta = json.loads(scene.grid_meta_json)
        origin = tuple(meta["origin"])
        cell_size = meta["cell_size"]
        col, row = world_to_grid(x, z, origin, cell_size)
        return row, col
    except Exception:
        return None, None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/scenes/{scene_id}/pois", response_model=list[POIResponse])
async def list_pois(scene_id: int, db: AsyncSession = Depends(get_db)):
    scene = await db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    result = await db.execute(select(POI).where(POI.scene_id == scene_id))
    return result.scalars().all()


@router.post("/scenes/{scene_id}/pois", response_model=POIResponse, status_code=201)
async def create_poi(scene_id: int, body: POICreate, db: AsyncSession = Depends(get_db)):
    scene = await db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    row, col = await _compute_grid_cell(scene, body.x, body.z)

    poi = POI(
        scene_id=scene_id,
        name=body.name,
        description=body.description,
        x=body.x,
        y=body.y,
        z=body.z,
        grid_row=row,
        grid_col=col,
    )
    db.add(poi)
    await db.commit()
    await db.refresh(poi)
    return poi


@router.put("/pois/{poi_id}", response_model=POIResponse)
async def update_poi(poi_id: int, body: POIUpdate, db: AsyncSession = Depends(get_db)):
    poi = await db.get(POI, poi_id)
    if not poi:
        raise HTTPException(status_code=404, detail="POI not found")

    if body.name is not None:
        poi.name = body.name
    if body.description is not None:
        poi.description = body.description
    if body.x is not None:
        poi.x = body.x
    if body.z is not None:
        poi.z = body.z
    if body.y is not None:
        poi.y = body.y

    # Recompute grid cell if position changed
    if body.x is not None or body.z is not None:
        scene = await db.get(Scene, poi.scene_id)
        if scene:
            row, col = await _compute_grid_cell(scene, poi.x, poi.z)
            poi.grid_row = row
            poi.grid_col = col

    await db.commit()
    await db.refresh(poi)
    return poi


@router.delete("/pois/{poi_id}", status_code=204)
async def delete_poi(poi_id: int, db: AsyncSession = Depends(get_db)):
    poi = await db.get(POI, poi_id)
    if not poi:
        raise HTTPException(status_code=404, detail="POI not found")
    await db.delete(poi)
    await db.commit()


@router.get("/scenes/{scene_id}/search", response_model=list[POIResponse])
async def search_pois(
    scene_id: int,
    q: str = Query("", description="Search query for POI name"),
    db: AsyncSession = Depends(get_db),
):
    scene = await db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    result = await db.execute(select(POI).where(POI.scene_id == scene_id))
    pois = result.scalars().all()

    if not q.strip() or not pois:
        return pois[:5]

    # Fuzzy match on POI names
    name_to_poi = {poi.name: poi for poi in pois}
    matches = fw_process.extract(q, list(name_to_poi.keys()), limit=5)
    matched_pois = [name_to_poi[name] for name, score in matches if score >= 40]
    return matched_pois
