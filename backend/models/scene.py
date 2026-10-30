"""
models/scene.py — SQLAlchemy ORM models for Scene and POI.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    glb_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    splat_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    grid_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    grid_meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tour_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    pois: Mapped[list["POI"]] = relationship("POI", back_populates="scene", cascade="all, delete-orphan")


class POI(Base):
    __tablename__ = "pois"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scene_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    x: Mapped[float] = mapped_column(Float, default=0.0)
    y: Mapped[float] = mapped_column(Float, default=0.0)
    z: Mapped[float] = mapped_column(Float, default=0.0)
    grid_col: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grid_row: Mapped[int | None] = mapped_column(Integer, nullable=True)

    scene: Mapped["Scene"] = relationship("Scene", back_populates="pois")
