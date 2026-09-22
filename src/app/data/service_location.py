"""ServiceLocation ORM model - a premise served by a transformer."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ServiceLocation(Base):
    __tablename__ = "service_locations"

    location_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    address: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    zip: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    location_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    transformer_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("grid_assets.asset_id", ondelete="SET NULL"),
        nullable=True,
    )

    transformer = relationship("GridAsset", back_populates="service_locations")
    meter = relationship("Meter", back_populates="location", uselist=False)
