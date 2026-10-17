from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ConnectError

from app.models.map_descendants_response import MapDescendantsResponse
from app.services.map_asset_service import MapAssetService


class TestMapAssetService:
    def _row(self, asset_id: str, asset_type: str = "TRANSFORMER", **fields: object) -> dict:
        return {
            "id": asset_id, "name": asset_id, "asset_type": asset_type,
            "lat": 32.4, "lng": -96.5, "status": "NORMAL", **fields,
        }

    @pytest.mark.asyncio
    async def test_returns_typed_distinct_descendants_and_keeps_missing_coordinates(self) -> None:
        client = MagicMock()
        child = self._row("TX-1", parent_id="F-1", lat=None, lng=None)
        client.run_sql = AsyncMock(return_value=[
            self._row("F-1", "FEEDER", in_outage=True),
            child, child,
            self._row("M-1", "METER", parent_id="TX-1", location_id="L-1"),
        ])
        result = await MapAssetService(client).get_descendants("F-1")
        assert isinstance(result, MapDescendantsResponse)
        assert result.source.in_outage
        assert [asset.id for asset in result.assets] == ["TX-1", "M-1"]
        assert result.assets[0].lat is None
        client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_leaf_returns_empty_descendants(self) -> None:
        client = MagicMock()
        client.run_sql = AsyncMock(return_value=[self._row("TX-1")])
        assert (await MapAssetService(client).get_descendants("TX-1")).assets == []

    @pytest.mark.asyncio
    async def test_unknown_asset_is_not_an_empty_success(self) -> None:
        client = MagicMock()
        client.run_sql = AsyncMock(return_value=[])
        with pytest.raises(LookupError, match="Asset not found"):
            await MapAssetService(client).get_descendants("missing")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("asset_id", ["", " ", "x" * 37])
    async def test_rejects_invalid_identifier(self, asset_id: str) -> None:
        client = MagicMock()
        with pytest.raises(ValueError):
            await MapAssetService(client).get_descendants(asset_id)
        client.run_sql.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("rows", [
        [{"id": "TX-1"}],
        ["not an object"],
        [{"id": "TX-1", "name": "TX-1", "asset_type": "TRANSFORMER", "status": "NORMAL", "lat": 100}],
    ])
    async def test_surfaces_malformed_results(self, rows: list) -> None:
        client = MagicMock()
        client.run_sql = AsyncMock(return_value=rows)
        with pytest.raises(RuntimeError, match="lookup failed"):
            await MapAssetService(client).get_descendants("TX-1")

    @pytest.mark.asyncio
    async def test_missing_source_is_a_query_failure(self) -> None:
        client = MagicMock()
        client.run_sql = AsyncMock(return_value=[self._row("other")])
        with pytest.raises(RuntimeError, match="missing its source"):
            await MapAssetService(client).get_descendants("TX-1")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error", [RuntimeError("offline"), ConnectError("offline")])
    async def test_mcp_failure_is_explicit(self, error: Exception) -> None:
        client = MagicMock()
        client.run_sql = AsyncMock(side_effect=error)
        with pytest.raises(RuntimeError, match="lookup failed"):
            await MapAssetService(client).get_descendants("TX-1")

    def test_fixed_query_escapes_identifier_and_does_not_depend_on_meter_view(self) -> None:
        sql = MapAssetService(MagicMock())._build_descendants_sql("TX'1")
        assert "asset_id = 'TX''1'" in sql
        assert "asset_meter_map" not in sql
        assert "child.parent_asset = root.asset_id" in sql
        assert "feeder.parent_asset = root.asset_id" in sql
        assert "sl.latitude" in sql and "sl.longitude" in sql
        assert "SELECT * FROM root UNION SELECT * FROM downstream_grid" in sql

    @pytest.mark.asyncio
    async def test_meter_id_collision_does_not_replace_or_remove_grid_source(self) -> None:
        client = MagicMock()
        client.run_sql = AsyncMock(return_value=[
            self._row("T-1", "METER"),
            self._row("T-1", "TRANSFORMER"),
        ])
        result = await MapAssetService(client).get_descendants("T-1")
        assert result.source.asset_type == "TRANSFORMER"
        assert len(result.assets) == 1
        assert result.assets[0].asset_type == "METER"
