"""EventType ORM model - lookup table for event categories."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class EventType(Base):
    __tablename__ = "event_types"

    event_type_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    description: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    events = relationship("Event", back_populates="event_type")
