"""
main.py — FastAPI application entry point for Namma Space.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import create_tables
from routers import navigation, pois, reconstruction, scenes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup."""
    await create_tables()
    yield


app = FastAPI(
    title="Namma Space API",
    description="Indoor spatial engine — scenes, POIs, navigation.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files ──────────────────────────────────────────────────────────────
from pathlib import Path
_public_static = Path(__file__).resolve().parent.parent / "frontend" / "public" / "static"
_static_dir = str(_public_static) if _public_static.is_dir() else "static"
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(scenes.router, prefix="/api", tags=["scenes"])
app.include_router(pois.router, prefix="/api", tags=["pois"])
app.include_router(navigation.router, prefix="/api", tags=["navigation"])
app.include_router(reconstruction.router, prefix="/api", tags=["reconstruction"])


@app.get("/api/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": "namma-space-api"}
