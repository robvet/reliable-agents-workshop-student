"""Event ORM model - a named incident (e.g. a storm) that groups related outages."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type_code: Mapped[Optional[str]] = mapped_column(
        String(30),
        ForeignKey("event_types.event_type_code", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    event_type = relationship("EventType", back_populates="events")
    outages = relationship("Outage", back_populates="event")
