"""Map asset retrieval service."""

import logging

from opentelemetry import trace

from ..tools.i_mcp_client import IMcpClient


class MapAssetService:
    """Loads map assets from MCP via a predefined SQL query."""

    def __init__(self, mcp_client: IMcpClient) -> None:
        self._mcp_client = mcp_client
        self._tracer = trace.get_tracer(__name__)
        self._map_assets_sql = (
            "SELECT "
            "ga.asset_id, "
            "ga.asset_name, "
            "ga.asset_type, "
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
            "WHERE ga.latitude IS NOT NULL "
            "AND ga.longitude IS NOT NULL"
        )

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
