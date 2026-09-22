"""Upstream MCP client — mcp_sql's only bridge to the pgEdge Postgres MCP
stdio subprocess.

Flat module, two functions. Per-call session: each call opens its own
stdio subprocess + ClientSession and tears it down when done. No pooling —
acceptable at this scale per the spec; do not add it.

pgEdge's `query_database` tool returns a *text* report, not structured JSON:

    Database: <redacted dsn>

    SQL Query:
    <sql> LIMIT <n>

    Results (<n> rows):
    <tab-separated header>
    <tab-separated values>
    ...

`_parse_query_result` turns that block into `list[dict]`. Empty cells are
returned as empty strings — pgEdge's text format cannot distinguish NULL
from an empty string, so callers should not rely on that distinction.
"""

import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import parsed_database_url, pgedge_bin

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolved_pgedge_bin() -> str:
    """Resolve PGEDGE_BIN relative to mcp_sql/ if it isn't already absolute."""
    path = pgedge_bin()
    return path if os.path.isabs(path) else os.path.join(_MODULE_DIR, path)


def _pgedge_env() -> dict:
    """Build the PGEDGE_DB_* env vars for the subprocess from DATABASE_URL."""
    db = parsed_database_url()
    env = os.environ.copy()
    env.update(
        {
            "PGEDGE_DB_HOST": db["host"],
            "PGEDGE_DB_PORT": str(db["port"]),
            "PGEDGE_DB_NAME": db["dbname"],
            "PGEDGE_DB_USER": db["user"],
            "PGEDGE_DB_PASSWORD": db["password"],
            "PGEDGE_DB_SSLMODE": "require",
            "PGEDGE_DB_ALLOW_WRITES": "false",
        }
    )
    return env


def _parse_query_result(text: str) -> list[dict]:
    """Parse pgEdge's `query_database` text report into a list of row dicts."""
    marker = "Results ("
    idx = text.find(marker)
    if idx == -1:
        return []

    lines = text[idx:].splitlines()[1:]  # drop the "Results (N rows):" line
    lines = [line for line in lines if line != ""]
    if not lines:
        return []

    header = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        values = line.split("\t")
        rows.append(dict(zip(header, values)))
    return rows


async def _call_tool(tool_name: str, arguments: dict) -> str:
    """Open a per-call stdio session to pgEdge and return the tool's text result.

    The RuntimeError below is deliberately raised *after* the stdio/session
    context managers have exited cleanly, not from within them. anyio wraps
    any exception raised inside those nested TaskGroups in an
    ExceptionGroup, which would stop callers from catching a plain
    RuntimeError.
    """
    params = StdioServerParameters(command=_resolved_pgedge_bin(), args=[], env=_pgedge_env())
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

    if result.isError:
        text = result.content[0].text if result.content else "unknown error"
        raise RuntimeError(f"{tool_name} failed: {text}")
    return result.content[0].text if result.content else ""


async def execute_sql(sql: str) -> list[dict]:
    """Execute sql via pgEdge's query_database tool and return parsed rows."""
    text = await _call_tool("query_database", {"query": sql})
    return _parse_query_result(text)


async def get_schema() -> str:
    """Fetch the DETAILED schema report (tables + columns + FKs) for the public schema.

    Without schema_name, get_schema_info returns only a table-name summary with no
    columns, which makes the NL2SQL model hallucinate column names (e.g. `id`).
    Passing schema_name yields the full column list so the model writes valid SQL.
    """
    return await _call_tool("get_schema_info", {"schema_name": "public"})
