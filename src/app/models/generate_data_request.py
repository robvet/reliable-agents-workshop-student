"""Request body for POST /generator/generate."""

from pydantic import BaseModel


class GenerateDataRequest(BaseModel):
    num_locations: int = 100
    crew_count: int = 20
    confirm: bool = False
