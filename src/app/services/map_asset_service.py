"""Map asset retrieval service."""

import logging

from httpx import HTTPError
from opentelemetry import trace
from pydantic import ValidationError

from ..models.map_asset import MapAsset
from ..models.map_descendants_response import MapDescendantsResponse
from ..models.map_snapshot_response import MapSnapshotResponse
from ..tools.i_mcp_client import IMcpClient


class MapAssetService:
    """Loads map assets from MCP via a predefined SQL query."""

    def __init__(self, mcp_client: IMcpClient) -> None:
        self._mcp_client = mcp_client
        self._tracer = trace.get_tracer(__name__)
        grid_assets_sql = (
            "SELECT "
            "ga.asset_id, "
            "ga.asset_name, "
            "ga.asset_type, "
            "ga.parent_asset, "
            "ga.region, "
            "ga.latitude, "
            "ga.longitude, "
            "ga.status, "
            "o.outage_id, "
            "c.crew_name "
            "FROM grid_assets ga "
            "LEFT JOIN LATERAL ("
            "SELECT out.outage_id FROM outages out "
            "JOIN outage_current_status ocs ON ocs.outage_id = out.outage_id "
            "WHERE out.asset_id = ga.asset_id "
            "AND ocs.status IN ('REPORTED','CONFIRMED','CREW_ASSIGNED') "
            "LIMIT 1"
            ") o ON TRUE "
            "LEFT JOIN LATERAL ("
            "SELECT wo.crew_id FROM work_orders wo "
            "WHERE wo.outage_id = o.outage_id "
            "ORDER BY wo.created_date DESC LIMIT 1"
            ") wo ON TRUE "
            "LEFT JOIN crews c ON c.crew_id = wo.crew_id "
        )
        self._map_assets_sql = (
            grid_assets_sql +
            "WHERE ga.latitude IS NOT NULL "
            "AND ga.longitude IS NOT NULL"
        )
        self._snapshot_sql = f"""
            WITH grid AS ({grid_assets_sql})
            SELECT asset_id AS id, COALESCE(asset_name, asset_id) AS name,
                   asset_type, parent_asset AS parent_id,
                   NULL AS location_id, latitude AS lat, longitude AS lng,
                   COALESCE(status, 'NORMAL') AS status,
                   outage_id IS NOT NULL AS in_outage, crew_name
            FROM grid
            UNION ALL
            SELECT m.meter_id, m.meter_id, 'METER', sl.transformer_id,
                   sl.location_id, sl.latitude, sl.longitude,
                   COALESCE(m.status, 'INACTIVE'), FALSE, NULL
            FROM meters m
            LEFT JOIN service_locations sl ON sl.location_id = m.location_id
            ORDER BY asset_type, id
        """

    async def get_assets(self) -> list[dict]:
        # This is the one hop where a failure is invisible: the browser just draws an
        # empty map. The span and the log lines make it obvious from stdout whether the
        # SQL ran at all, and how many rows came back.
        with self._tracer.start_as_current_span("map_assets.load") as span:
            logging.info("MapAssetService.get_assets: querying MCP for map assets")
            try:
                rows = await self._mcp_client.run_sql(self._map_assets_sql)
            except Exception as ex:
                span.set_attribute("success", False)
                logging.exception("MapAssetService.get_assets: MCP run_sql failed")
                raise RuntimeError(f"MCP run_sql failed for map assets: {ex}") from ex

            assets: list[dict] = []
            for row in rows:
                if not isinstance(row, dict):
                    span.set_attribute("success", False)
                    logging.error("MapAssetService.get_assets: non-object row from MCP")
                    raise RuntimeError("MCP map query returned a non-object row")

                asset_id = row.get("asset_id") or row.get("id")
                asset_name = row.get("asset_name") or row.get("name")
                assets.append(
                    {
                        "id": asset_id or "",
                        "name": asset_name or asset_id or "",
                        "asset_type": row.get("asset_type") or "",
                        "region": row.get("region") or "",
                        "lat": row.get("latitude"),
                        "lng": row.get("longitude"),
                        "status": row.get("status") or "NORMAL",
                        "in_outage": bool(row.get("outage_id")),
                        "crew_name": row.get("crew_name"),
                    }
                )

            span.set_attribute("success", True)
            span.set_attribute("map_assets.row_count", len(assets))
            logging.info("MapAssetService.get_assets: returned %d assets", len(assets))
            return assets

    async def get_snapshot(self) -> MapSnapshotResponse:
        """Load grid assets and meters together; retain no server-side cache."""
        with self._tracer.start_as_current_span("map_assets.snapshot") as span:
            logging.info("MapAssetService.get_snapshot: querying MCP for map snapshot")
            try:
                rows = await self._mcp_client.run_sql(self._snapshot_sql)
                snapshot = MapSnapshotResponse(
                    assets=[MapAsset.model_validate(row) for row in rows],
                )
            except (RuntimeError, ValidationError, TypeError, HTTPError, OSError) as ex:
                span.set_attribute("success", False)
                logging.exception("MapAssetService.get_snapshot: lookup failed")
                raise RuntimeError("Map snapshot lookup failed") from ex

            span.set_attribute("success", True)
            span.set_attribute("map_assets.row_count", len(snapshot.assets))
            logging.info("MapAssetService.get_snapshot: returned %d assets", len(snapshot.assets))
            return snapshot

    async def get_descendants(self, asset_id: str) -> MapDescendantsResponse:
        """Read the fixed-depth topology without routing through an agent."""
        if not asset_id.strip() or len(asset_id) > 36:
            logging.warning("MapAssetService.get_descendants: invalid asset identifier")
            raise ValueError("Asset identifier must contain between 1 and 36 characters")

        with self._tracer.start_as_current_span("map_assets.descendants") as span:
            span.set_attribute("asset_id", asset_id)
            try:
                rows = await self._mcp_client.run_sql(self._build_descendants_sql(asset_id))
                assets = [MapAsset.model_validate(row) for row in rows]
            except (RuntimeError, ValidationError, TypeError, HTTPError, OSError) as ex:
                span.set_attribute("success", False)
                logging.exception("MapAssetService.get_descendants: lookup failed")
                raise RuntimeError("Downstream asset lookup failed") from ex

            source = next(
                (asset for asset in assets if asset.id == asset_id and asset.asset_type != "METER"),
                None,
            )
            if source is None:
                if assets:
                    logging.error("MapAssetService.get_descendants: result missing source asset")
                    span.set_attribute("success", False)
                    raise RuntimeError("Downstream asset result missing its source")
                span.set_attribute("success", False)
                logging.info("MapAssetService.get_descendants: asset not found: %s", asset_id)
                raise LookupError("Asset not found")

            descendants = {
                (asset.asset_type, asset.id): asset
                for asset in assets
                if (asset.asset_type, asset.id) != (source.asset_type, source.id)
            }
            span.set_attribute("success", True)
            span.set_attribute("map_assets.descendant_count", len(descendants))
            return MapDescendantsResponse(source=source, assets=list(descendants.values()))

    def _build_descendants_sql(self, asset_id: str) -> str:
        # IMcpClient.run_sql accepts SQL only, not bind parameters.
        safe_id = asset_id.replace("'", "''")
        return f"""
            WITH root AS (
                SELECT * FROM grid_assets WHERE asset_id = '{safe_id}'
            ), downstream_grid AS (
                SELECT child.*
                FROM grid_assets child JOIN root ON child.parent_asset = root.asset_id
                WHERE (root.asset_type = 'SUBSTATION' AND child.asset_type = 'FEEDER')
                   OR (root.asset_type = 'FEEDER' AND child.asset_type = 'TRANSFORMER')
                UNION
                SELECT xfmr.*
                FROM grid_assets xfmr
                JOIN grid_assets feeder ON xfmr.parent_asset = feeder.asset_id
                JOIN root ON feeder.parent_asset = root.asset_id
                WHERE root.asset_type = 'SUBSTATION'
                  AND feeder.asset_type = 'FEEDER'
                  AND xfmr.asset_type = 'TRANSFORMER'
            ), selected_grid AS (
                SELECT * FROM root UNION SELECT * FROM downstream_grid
            )
            SELECT ga.asset_id AS id, COALESCE(ga.asset_name, ga.asset_id) AS name,
                   ga.asset_type, ga.parent_asset AS parent_id,
                   NULL AS location_id, ga.latitude AS lat, ga.longitude AS lng,
                   COALESCE(ga.status, 'NORMAL') AS status,
                   EXISTS (
                       SELECT 1 FROM outages o
                       JOIN outage_current_status ocs ON ocs.outage_id = o.outage_id
                       WHERE o.asset_id = ga.asset_id
                         AND ocs.status IN ('REPORTED', 'CONFIRMED', 'CREW_ASSIGNED')
                   ) AS in_outage
            FROM selected_grid ga
            UNION ALL
            SELECT m.meter_id, m.meter_id, 'METER', sl.transformer_id,
                   sl.location_id, sl.latitude, sl.longitude,
                   COALESCE(m.status, 'INACTIVE'), FALSE
            FROM selected_grid xfmr
            JOIN service_locations sl ON sl.transformer_id = xfmr.asset_id
            JOIN meters m ON m.location_id = sl.location_id
            WHERE xfmr.asset_type = 'TRANSFORMER'
            ORDER BY asset_type, id
        """
