"""Telemetry setup for mcp_sql.

Flat module — mirrors the spec's own snippet almost verbatim. Telemetry is
best-effort: if APPLICATIONINSIGHTS_CONNECTION_STRING is absent, the server
still starts and logs to stdout instead.
"""

import logging

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

from config import application_insights_connection_string

_configured = False


def setup() -> None:
    """Wire Azure Monitor OpenTelemetry if a connection string is present."""
    global _configured
    if _configured:
        return

    connection_string = application_insights_connection_string()
    if connection_string:
        # Pass connection_string explicitly rather than relying on the
        # ambient APPLICATIONINSIGHTS_CONNECTION_STRING env var — confirmed
        # necessary in Task 2 (see mcp_sql/README.md notes).
        configure_azure_monitor(
            logger_name="mcp_sql",
            connection_string=connection_string,
            enable_live_metrics=False,
        )

    logging.getLogger("mcp_sql").setLevel(logging.INFO)
    _configured = True


tracer = trace.get_tracer("mcp_sql")
log = logging.getLogger("mcp_sql")
