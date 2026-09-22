"""Outage ORM model - a thin record linking an event to an impacted asset.

Status lives in outage_status_log, not here - see OutageStatusLog.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Outage(Base):
    __tablename__ = "outages"

    outage_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("events.event_id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("grid_assets.asset_id", ondelete="SET NULL"),
        nullable=True,
    )
    impact_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    impact_magnitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    asset = relationship("GridAsset", back_populates="outages")
    event = relationship("Event", back_populates="outages")
    work_orders = relationship("WorkOrder", back_populates="outage")
    status_log = relationship("OutageStatusLog", back_populates="outage")
