"""
routers/scenes.py — Scene CRUD routes.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.scene import Scene

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SceneCreate(BaseModel):
    name: str
    glb_path: str | None = None
    splat_path: str | None = None
    grid_path: str | None = None
    grid_meta_json: str | None = None
    tour_path: str | None = None


class SceneResponse(BaseModel):
    id: int
    name: str
    glb_path: str | None
    splat_path: str | None
    grid_path: str | None
    grid_meta_json: str | None
    tour_path: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/scenes", response_model=list[SceneResponse])
async def list_scenes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Scene).order_by(Scene.created_at.desc()))
    return result.scalars().all()


@router.post("/scenes", response_model=SceneResponse, status_code=201)
async def create_scene(body: SceneCreate, db: AsyncSession = Depends(get_db)):
    # Use defaults for paths if not provided
    glb = body.glb_path or "/static/models/scene.glb"
    splat = body.splat_path or "/static/models/scene.splat"
    grid = body.grid_path or "/static/navigation/grid.npy"

    scene = Scene(
        name=body.name,
        glb_path=glb,
        splat_path=splat,
        grid_path=grid,
        grid_meta_json=body.grid_meta_json,
        tour_path=body.tour_path,
    )
    db.add(scene)
    await db.commit()
    await db.refresh(scene)
    return scene


@router.get("/scenes/{scene_id}", response_model=SceneResponse)
async def get_scene(scene_id: int, db: AsyncSession = Depends(get_db)):
    scene = await db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene
