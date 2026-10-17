from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import ApiRoutes
from app.models.map_asset import MapAsset
from app.models.map_descendants_response import MapDescendantsResponse
from app.models.map_snapshot_response import MapSnapshotResponse


class TestMapDescendantsRoutes:
    def _client(self, service: MagicMock) -> TestClient:
        routes = ApiRoutes(
            orchestrator=MagicMock(), prompt_library_service=MagicMock(),
            map_asset_service=service, weather_client=MagicMock(),
        )
        app = FastAPI()
        app.include_router(routes.router)
        return TestClient(app)

    def test_serializes_typed_response(self) -> None:
        service = MagicMock()
        service.get_descendants = AsyncMock(return_value=MapDescendantsResponse(
            source=MapAsset(id="T-1", name="Transformer", asset_type="TRANSFORMER", status="NORMAL"),
            assets=[],
        ))
        response = self._client(service).get("/map/assets/T-1/descendants")
        assert response.status_code == 200
        assert response.json()["source"]["id"] == "T-1"
        assert response.json()["assets"] == []
        service.get_descendants.assert_awaited_once_with("T-1")

    def test_serializes_snapshot_with_meters_and_parent_ids(self) -> None:
        service = MagicMock()
        service.get_snapshot = AsyncMock(return_value=MapSnapshotResponse(assets=[
            MapAsset(id="T-1", name="Transformer", asset_type="TRANSFORMER", status="REPORTED", in_outage=True),
            MapAsset(id="M-1", name="Meter", asset_type="METER", parent_id="T-1", status="ACTIVE"),
        ]))
        response = self._client(service).get("/map/snapshot")
        assert response.status_code == 200
        assert response.json()["assets"][0]["in_outage"] is True
        assert response.json()["assets"][1]["parent_id"] == "T-1"
        service.get_snapshot.assert_awaited_once_with()

    def test_snapshot_error_returns_502(self) -> None:
        service = MagicMock()
        service.get_snapshot = AsyncMock(side_effect=RuntimeError("Map snapshot lookup failed"))
        response = self._client(service).get("/map/snapshot")
        assert response.status_code == 502
        assert response.json()["detail"] == "Map snapshot lookup failed"

    @pytest.mark.parametrize(("error", "status"), [
        (ValueError("Invalid identifier"), 422),
        (LookupError("Asset not found"), 404),
        (RuntimeError("Downstream asset lookup failed"), 502),
    ])
    def test_returns_explicit_errors(self, error: Exception, status: int) -> None:
        service = MagicMock()
        service.get_descendants = AsyncMock(side_effect=error)
        response = self._client(service).get("/map/assets/T-1/descendants")
        assert response.status_code == status
        assert response.json()["detail"] == str(error)
