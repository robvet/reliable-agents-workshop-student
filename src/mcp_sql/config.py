"""Environment configuration loading for mcp_sql.

Flat module, module-level functions only — mcp_sql is exempt from the
one-class-per-file rule (see AGENTS.md). All config comes from env vars /
.env; nothing here talks to a network.
"""

import os
import re
from urllib.parse import urlsplit, unquote

from dotenv import load_dotenv

load_dotenv()


def database_url() -> str:
    """Return the raw DATABASE_URL. Single source of truth for DB credentials."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def parsed_database_url() -> dict:
    """Split DATABASE_URL into its components, percent-decoding user/password."""
    parts = urlsplit(database_url())
    return {
        "user": unquote(parts.username) if parts.username else None,
        "password": unquote(parts.password) if parts.password else None,
        "host": parts.hostname,
        "port": parts.port or 5432,
        "dbname": parts.path.lstrip("/"),
    }


def mcp_openai_endpoint() -> str:
    """Azure AI Foundry endpoint used for the single nl2sql LLM call."""
    endpoint = os.environ.get("MCP_OPENAI_ENDPOINT")
    if not endpoint:
        raise RuntimeError("MCP_OPENAI_ENDPOINT is not set")
    return endpoint.strip()


def inference_lm_deployment() -> str:
    """Deployment/model name for the nl2sql LLM call."""
    deployment = os.environ.get("INFERENCE_LM_DEPLOYMENT")
    if not deployment:
        raise RuntimeError("INFERENCE_LM_DEPLOYMENT is not set")
    return deployment


def application_insights_connection_string() -> str | None:
    """Optional App Insights connection string. Telemetry must never block startup."""
    return os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")


def max_rows() -> int:
    """Row cap applied to every result set. Defaults to 100."""
    return int(os.environ.get("MAX_ROWS", "100"))


def pgedge_bin() -> str:
    """Path to the pgedge-postgres-mcp binary."""
    return os.environ.get("PGEDGE_BIN", "./pgedge-postgres-mcp")


def pgedge_config() -> str | None:
    """Optional path to a pgedge YAML config file (only used if env vars don't work)."""
    return os.environ.get("PGEDGE_CONFIG")


def redact(url: str) -> str:
    """Mask the password in a connection URL so it is never logged or traced."""
    return re.sub(r"(://[^:/@]+:)([^@]+)(@)", r"\1***\3", url)
