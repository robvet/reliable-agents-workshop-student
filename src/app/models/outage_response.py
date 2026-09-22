"""Response body describing an outage, returned by the outage endpoints."""

from typing import Optional

from pydantic import BaseModel


class OutageResponse(BaseModel):
    outage_id: str
    asset_id: Optional[str] = None
    event_id: str
    impact_count: Optional[int] = None
    impact_magnitude: Optional[float] = None
    status: Optional[str] = None
    event_name: Optional[str] = None
    event_severity: Optional[str] = None
    crew_name: Optional[str] = None

    model_config = {"from_attributes": True}
