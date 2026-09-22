"""Meter ORM model - the metering device installed at a service location."""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Meter(Base):
    __tablename__ = "meters"

    meter_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    location_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("service_locations.location_id", ondelete="SET NULL"),
        nullable=True,
    )
    meter_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    communication_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    install_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    location = relationship("ServiceLocation", back_populates="meter")
