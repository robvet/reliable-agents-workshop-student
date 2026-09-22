"""Request body for POST /outages."""

from typing import Optional

from pydantic import BaseModel


class CreateOutageRequest(BaseModel):
    asset_id: str
    # None -> OutageLifecycleService creates a default LOW-severity event instead
    # of requiring the caller to pick one.
    event_id: Optional[str] = None
    impact_count: Optional[int] = None
    impact_magnitude: Optional[float] = None
