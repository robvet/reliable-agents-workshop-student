"""Complete map data for local filtering and downstream selection."""

from pydantic import BaseModel

from .map_asset import MapAsset


class MapSnapshotResponse(BaseModel):
    assets: list[MapAsset]
