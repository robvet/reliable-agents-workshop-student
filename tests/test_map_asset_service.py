from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ConnectError

from app.models.map_descendants_response import MapDescendantsResponse
from app.models.map_snapshot_response import MapSnapshotResponse
from app.services.map_asset_service import MapAssetService


class TestMapAssetService:
    def _row(self, asset_id: str, asset_type: str = "TRANSFORMER", **fields: object) -> dict:
        return {
            "id": asset_id, "name": asset_id, "asset_type": asset_type,
            "lat": 32.4, "lng": -96.5, "status": "NORMAL", **fields,
        }

    @pytest.mark.asyncio
    async def test_snapshot_returns_grid_and_meters_with_parent_links_and_recorded_status(self) -> None:
        rows = [
            self._row("S-1", "SUBSTATION", parent_id=None, in_outage=True),
            self._row("F-1", "FEEDER", parent_id="S-1"),
            self._row("T-1", parent_id="F-1", crew_name="Crew One"),
            self._row("M-1", "METER", parent_id="T-1", location_id="L-1", status="ACTIVE"),
        ]
        client = MagicMock()
        client.run_sql = AsyncMock(return_value=rows)
        result = await MapAssetService(client).get_snapshot()
        assert isinstance(result, MapSnapshotResponse)
        assert [asset.id for asset in result.assets] == ["S-1", "F-1", "T-1", "M-1"]
        assert result.assets[0].in_outage is True
        assert result.assets[1].in_outage is False
        assert result.assets[2].crew_name == "Crew One"
        assert result.assets[3].parent_id == "T-1"
        assert result.assets[3].location_id == "L-1"
        assert result.assets[3].status == "ACTIVE"
        client.run_sql.assert_awaited_once()
        client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_snapshot_retains_missing_coordinates_and_empty_branches(self) -> None:
        client = MagicMock()
        client.run_sql = AsyncMock(return_value=[
            self._row("F-empty", "FEEDER", lat=None, lng=None),
            self._row("T-bare", parent_id="F-empty"),
            self._row("M-unlocated", "METER", parent_id=None, lat=None, lng=None),
        ])
        result = await MapAssetService(client).get_snapshot()
        assert len(result.assets) == 3
        assert result.assets[0].lat is None
        assert result.assets[1].parent_id == "F-empty"

    @pytest.mark.asyncio
    async def test_empty_snapshot_is_valid_and_each_call_queries_mcp(self) -> None:
        client = MagicMock()
        client.run_sql = AsyncMock(return_value=[])
        service = MapAssetService(client)
        assert (await service.get_snapshot()).assets == []
        assert (await service.get_snapshot()).assets == []
        assert client.run_sql.await_count == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize("rows", [
        ["not an object"],
        [{"id": "broken"}],
        [{"id": "T-1", "name": "T-1", "asset_type": "TRANSFORMER", "status": "NORMAL", "lat": 100}],
    ])
    async def test_snapshot_surfaces_malformed_rows(self, rows: list) -> None:
        client = MagicMock()
        client.run_sql = AsyncMock(return_value=rows)
        with pytest.raises(RuntimeError, match="Map snapshot lookup failed"):
            await MapAssetService(client).get_snapshot()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error", [RuntimeError("offline"), ConnectError("offline")])
    async def test_snapshot_surfaces_mcp_errors(self, error: Exception) -> None:
        client = MagicMock()
        client.run_sql = AsyncMock(side_effect=error)
        with pytest.raises(RuntimeError, match="Map snapshot lookup failed"):
            await MapAssetService(client).get_snapshot()

    def test_snapshot_query_is_fixed_and_grid_portion_does_not_require_meters(self) -> None:
        sql = MapAssetService(MagicMock())._snapshot_sql
        assert "ga.parent_asset" in sql
        assert "parent_asset AS parent_id" in sql
        assert "outage_id IS NOT NULL AS in_outage" in sql
        assert "WHERE ga.latitude IS NOT NULL" not in sql
        assert "UNION ALL" in sql
        assert "LEFT JOIN service_locations sl ON sl.location_id = m.location_id" in sql
        assert "asset_meter_map" not in sql

    @pytest.mark.asyncio
    async def test_legacy_asset_list_keeps_its_existing_shape_and_coordinate_filter(self) -> None:
        client = MagicMock()
        client.run_sql = AsyncMock(return_value=[{
            "asset_id": "T-1", "asset_name": "Transformer", "asset_type": "TRANSFORMER",
            "parent_asset": "F-1", "region": "North", "latitude": 32.4, "longitude": -96.5,
            "status": "REPORTED", "outage_id": "O-1", "crew_name": "Crew One",
        }])
        result = await MapAssetService(client).get_assets()
        assert result == [{
            "id": "T-1", "name": "Transformer", "asset_type": "TRANSFORMER",
            "region": "North", "lat": 32.4, "lng": -96.5,
            "status": "REPORTED", "in_outage": True, "crew_name": "Crew One",
        }]
        assert "WHERE ga.latitude IS NOT NULL AND ga.longitude IS NOT NULL" in client.run_sql.await_args.args[0]

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
