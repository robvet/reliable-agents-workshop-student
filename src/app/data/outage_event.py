"""OutageStatusLog ORM model - the restoration-status ledger for one outage.

Current status is derived (see outage_current_status view), never cached here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class OutageStatusLog(Base):
    __tablename__ = "outage_status_log"

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    outage_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("outages.outage_id", ondelete="CASCADE"),
    )
    event_type: Mapped[str] = mapped_column(String(30))
    from_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    etr: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    outage = relationship("Outage", back_populates="status_log")
