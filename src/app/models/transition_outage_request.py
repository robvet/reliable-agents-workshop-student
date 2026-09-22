"""Request body for POST /outages/{outage_id}/transition."""

from typing import Optional

from pydantic import BaseModel


class TransitionOutageRequest(BaseModel):
    to_status: str
    note: Optional[str] = None
    crew_id: Optional[str] = None
