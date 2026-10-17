"""Response contract for the deterministic downstream map lookup."""

from pydantic import BaseModel

from .map_asset import MapAsset


class MapDescendantsResponse(BaseModel):
    source: MapAsset
    assets: list[MapAsset]

