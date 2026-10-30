"""
database.py — Async SQLAlchemy setup for Namma Space.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///./namma_space.db"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def create_tables() -> None:
    """Create all SQLAlchemy tables if they don't exist yet."""
    from models import scene as _  # noqa: F401 — ensure models are registered
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """FastAPI dependency — yields an async database session."""
    async with AsyncSessionLocal() as session:
        yield session
