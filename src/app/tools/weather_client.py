"""WeatherClient: the app-side client for NWS (National Weather Service) alerts."""

import httpx

# *********************************************
# *********  Architectural Insights *************
# *********************************************
# Role: the app's outbound adapter to the public NWS alerts API. Callers (the
# /map/weather route, WeatherAgent) depend on THIS class, not on the NWS wire
# format - the GeoJSON parsing stays sealed behind get_active_alerts().
#
# Lifetime: constructed once in the composition root and shared as an
# app-lifetime singleton, same as McpClient. Stateless: base_url/timeouts are
# write-once config, each get_active_alerts() call opens and closes its own
# httpx client as a local.
#
# Demo mode mirrors Settings.mcp_enabled's stub-fallback pattern: when enabled,
# a hardcoded preset alert is returned instead of calling NWS, so the feature is
# demoable regardless of real weather.

# Preset alerts for demo_mode. Small polygon sized to a dense asset cluster near
# Duncanville/Lancaster (verified against real seeded asset coordinates, not the
# full DFW bounding box) so it visibly overlaps ~15 assets without covering half
# the map. GeoJSON ring coordinates are [lng, lat] pairs, closed.
_DEMO_PRESETS: dict[str, dict] = {
    "north_region_severe_tstorm": {
        "event": "Severe Thunderstorm Warning",
        "severity": "Severe",
        "headline": "Severe Thunderstorm Warning issued for the North region (demo alert)",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-96.87, 32.55],
                    [-96.76, 32.55],
                    [-96.76, 32.66],
                    [-96.87, 32.66],
                    [-96.87, 32.55],
                ]
            ],
        },
    },
}


class WeatherClient:
    """Fetches active NWS alerts (or a hardcoded demo preset) for a US state area."""

    def __init__(
        self,
        base_url: str,
        timeout: float,
        connect_timeout: float,
        demo_mode: bool = False,
        demo_preset: str = "north_region_severe_tstorm",
    ) -> None:
        """Store connection config. No network I/O here (client opens per call)."""
        self._base_url = base_url
        self._timeout = timeout
        self._connect_timeout = connect_timeout
        self._demo_mode = demo_mode
        self._demo_preset = demo_preset

    async def get_active_alerts(self, area: str = "TX", force_demo: bool = False) -> list[dict]:
        """Return active alerts as a list of {event, severity, headline, geometry} dicts.

        In demo mode (configured or force_demo=True for this one call), returns the
        preset with no network call. force_demo lets a caller (the /map/weather route,
        via its own ?demo=true query param) trigger the preset on demand for a live
        demo without restarting the app or changing weather_demo_mode - no state is
        stored, it only affects this one call.
        In real mode, calls NWS and raises RuntimeError on any failure - callers
        decide fallback behavior, this method never silently swallows an error.
        """
        if self._demo_mode or force_demo:
            preset = _DEMO_PRESETS.get(self._demo_preset)
            if preset is None:
                raise RuntimeError(
                    f"Unknown weather demo preset: {self._demo_preset!r} "
                    f"(known presets: {sorted(_DEMO_PRESETS)})"
                )
            return [preset]

        timeout = httpx.Timeout(self._timeout, connect=self._connect_timeout)
        try:
            async with httpx.AsyncClient(timeout=timeout) as http_client:
                response = await http_client.get(
                    f"{self._base_url}/alerts/active", params={"area": area}
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as ex:
            raise RuntimeError(f"NWS alerts request failed: {ex}") from ex

        features = payload.get("features")
        if not isinstance(features, list):
            raise RuntimeError("NWS alerts response missing a 'features' list")

        alerts: list[dict] = []
        for feature in features:
            properties = feature.get("properties") or {}
            geometry = feature.get("geometry")
            if geometry is None:
                # Some NWS alerts (e.g. statewide) omit geometry entirely - not
                # useful for point-in-polygon matching, so skip them here.
                continue
            alerts.append(
                {
                    "event": properties.get("event") or "",
                    "severity": properties.get("severity") or "Unknown",
                    "headline": properties.get("headline") or "",
                    "geometry": geometry,
                }
            )

        return alerts
