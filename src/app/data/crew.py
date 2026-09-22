"""Crew ORM model - a field crew available for outage work orders."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Crew(Base):
    __tablename__ = "crews"

    crew_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    crew_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    crew_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    base_location: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    crew_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    supervisor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    work_orders = relationship("WorkOrder", back_populates="crew")
