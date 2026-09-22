"""WeatherAgent: correlates active NWS alerts with real asset locations."""

import logging

from opentelemetry import trace
from shapely.geometry import Point, shape

from ..models.agent_request import AgentRequest
from ..models.agent_result import AgentResult
from ..models.trace_step import TraceStep
from ..services.map_asset_service import MapAssetService
from ..tools.weather_client import WeatherClient
from .base_domain_agent import BaseDomainAgent


class WeatherAgent(BaseDomainAgent):
    """Reports active weather alerts that actually overlap monitored assets.

    Speaks in domain terms only (alerts, affected assets). It does not reason
    about the polygons itself beyond point-in-polygon containment - "TX has an
    alert somewhere" is not actionable, so this agent always resolves alerts
    down to the concrete assets, if any, inside each alert's polygon.
    """

    name = "weather"
    description = "Reports active weather alerts and which monitored assets, if any, fall inside them."

    def __init__(self, weather_client: WeatherClient, map_asset_service: MapAssetService):
        # inject both collaborators so the agent stays testable and never news up its own clients
        self._weather_client = weather_client
        self._map_asset_service = map_asset_service
        self._tracer = trace.get_tracer(__name__)

    async def handle(self, request: AgentRequest) -> AgentResult:
        with self._tracer.start_as_current_span("weather_agent.handle") as span:
            try:
                alerts = await self._weather_client.get_active_alerts()
                assets = await self._map_asset_service.get_assets()
            except Exception:
                # Cannot process a step with no data - record the fault and fail the
                # request. The orchestrator turns this into an error event and stops.
                span.set_attribute("weather.success", False)
                logging.exception("WeatherAgent: fetching alerts or assets failed; failing the step")
                raise

            matches = self._match_alerts_to_assets(alerts, assets)

            span.set_attribute("weather.alert_count", len(alerts))
            span.set_attribute("weather.matched_alert_count", len(matches))
            span.set_attribute("weather.success", True)
            logging.info(
                "WeatherAgent: alerts=%d matched=%d", len(alerts), len(matches)
            )

            data = {"matches": matches, "alert_count": len(alerts)}
            return self._result(
                data=data,
                ok=True,
                summary=self._summarize(matches),
                detail={
                    "alert_count": str(len(alerts)),
                    "matched_alert_count": str(len(matches)),
                },
            )

    # --- helpers -----------------------------------------------------------

    def _match_alerts_to_assets(self, alerts: list[dict], assets: list[dict]) -> list[dict]:
        """For each alert, find which assets (if any) fall inside its polygon."""
        matches: list[dict] = []
        for alert in alerts:
            try:
                polygon = shape(alert["geometry"])
            except Exception:
                # Malformed/unsupported geometry for this one alert - skip it rather
                # than fail the whole step over a single bad feature.
                logging.warning("WeatherAgent: skipping alert with unusable geometry")
                continue

            affected = [
                asset
                for asset in assets
                if asset.get("lat") is not None
                and asset.get("lng") is not None
                and polygon.contains(Point(asset["lng"], asset["lat"]))
            ]
            if affected:
                matches.append(
                    {
                        "event": alert["event"],
                        "severity": alert["severity"],
                        "headline": alert["headline"],
                        "affected_assets": affected,
                    }
                )
        return matches

    def _summarize(self, matches: list[dict]) -> str:
        if not matches:
            return "no active alerts affecting monitored assets"
        parts = []
        for match in matches:
            names = ", ".join(a["name"] for a in match["affected_assets"])
            parts.append(
                f"{match['event']} — {len(match['affected_assets'])} assets affected: {names}"
            )
        return "; ".join(parts)

    def _result(self, data: dict, ok: bool, summary: str, detail: dict | None = None) -> AgentResult:
        return AgentResult(
            agent=self.name,
            data=data,
            success=ok,
            trace_step=TraceStep(
                agent=self.name,
                action="match_alerts",
                summary=summary,
                success=ok,
                detail=detail,
            ),
        )
