"""GridAsset ORM model - substation, feeder, or transformer node."""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from .base import Base


class GridAsset(Base):
    __tablename__ = "grid_assets"

    asset_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset_type: Mapped[str] = mapped_column(String(50))
    asset_name: Mapped[str] = mapped_column(String(120))
    parent_asset: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("grid_assets.asset_id", ondelete="SET NULL"),
        nullable=True,
    )
    voltage_kv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rated_capacity_kva: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    install_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    # Lifecycle: is this asset commissioned and in service? Unrelated to outages.
    asset_condition: Mapped[str] = mapped_column(String(30))
    # Real-time outage state, kept in sync by OutageLifecycleService. NORMAL = no
    # open outage. See docs/business-rules/asset-status-business-rules.md.
    status: Mapped[str] = mapped_column(String(30))
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    children = relationship(
        "GridAsset",
        backref=backref("parent", remote_side=[asset_id]),
        foreign_keys=[parent_asset],
    )
    outages = relationship("Outage", back_populates="asset")
    work_orders = relationship("WorkOrder", back_populates="asset")
    service_locations = relationship("ServiceLocation", back_populates="transformer")
