"""A grid asset or meter returned by a map lookup."""

from typing import Literal

from pydantic import BaseModel, Field


class MapAsset(BaseModel):
    id: str = Field(min_length=1)
    name: str
    asset_type: Literal["SUBSTATION", "FEEDER", "TRANSFORMER", "METER"]
    parent_id: str | None = None
    location_id: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    lng: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    status: str
    in_outage: bool = False
    crew_name: str | None = None
