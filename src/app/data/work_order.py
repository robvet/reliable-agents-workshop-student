"""WorkOrder ORM model - a crew work order created to restore an outage."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class WorkOrder(Base):
    __tablename__ = "work_orders"

    work_order_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    outage_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("outages.outage_id", ondelete="SET NULL"),
        nullable=True,
    )
    asset_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("grid_assets.asset_id", ondelete="SET NULL"),
        nullable=True,
    )
    crew_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("crews.crew_id", ondelete="SET NULL"),
        nullable=True,
    )
    wo_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    estimated_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    outage = relationship("Outage", back_populates="work_orders")
    asset = relationship("GridAsset", back_populates="work_orders")
    crew = relationship("Crew", back_populates="work_orders")
