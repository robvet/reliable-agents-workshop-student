"""FastMCP server for mcp_sql — the guard and the two tools.

Flat module. Streamable HTTP transport on port 8000, mounted at /mcp.

Two tools:
- run_sql(query): execute a caller-supplied SQL string. No LLM.
- ask(question): nl2sql.to_sql() writes SQL, guard checks it, execute_sql runs it.

The read-only DB grant + pgEdge's own allow_writes=false are the real
security boundary. `check()` here is a fast-fail convenience, not the
security boundary (see README).
"""

import time

from fastmcp import FastMCP

import nl2sql
import upstream
from config import max_rows
from telemetry import log, setup as setup_telemetry, tracer

setup_telemetry()

mcp = FastMCP("mcp_sql")

# Schema cache for ask(). Fetched lazily on the first ask() call, not at
# startup — run_sql and server boot never pay for a schema fetch they may
# not need.
_schema_cache: str | None = None


async def _cached_schema() -> str:
    """Return get_schema_info's output, fetching and caching it on first use."""
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = await upstream.get_schema()
    return _schema_cache


def check(sql: str) -> None:
    """Read-only, single-statement guard. Fast fail, not the security boundary."""
    s = sql.strip().rstrip(";").lower()
    if not (s.startswith("select") or s.startswith("with")):
        raise ValueError("read-only: SELECT/WITH only")
    if ";" in s:
        raise ValueError("single statement only")


def _with_limit(sql: str, limit: int) -> str:
    """Append LIMIT {limit} to sql if it doesn't already specify one."""
    s = sql.strip().rstrip(";")
    if "limit" in s.lower():
        return s
    return f"{s} LIMIT {limit}"


@mcp.tool
async def run_sql(query: str) -> list[dict]:
    """Execute a read-only SQL SELECT/WITH statement. No LLM involved."""
    start = time.perf_counter()
    with tracer.start_as_current_span("run_sql") as span:
        span.set_attribute("mcp.tool", "run_sql")
        span.set_attribute("db.statement", query)
        try:
            check(query)
        except ValueError as ex:
            elapsed_ms = (time.perf_counter() - start) * 1000
            log.info(
                "tool_call",
                extra={
                    "tool": "run_sql",
                    "sql": query,
                    "elapsed_ms": elapsed_ms,
                    "outcome": "blocked",
                },
            )
            span.set_attribute("mcp.row_count", 0)
            raise

        try:
            rows = await upstream.execute_sql(_with_limit(query, max_rows()))
            elapsed_ms = (time.perf_counter() - start) * 1000
            span.set_attribute("mcp.row_count", len(rows))
            log.info(
                "tool_call",
                extra={
                    "tool": "run_sql",
                    "sql": query,
                    "row_count": len(rows),
                    "elapsed_ms": elapsed_ms,
                    "outcome": "ok",
                },
            )
            return rows
        except Exception as ex:
            elapsed_ms = (time.perf_counter() - start) * 1000
            log.info(
                "tool_call",
                extra={
                    "tool": "run_sql",
                    "sql": query,
                    "elapsed_ms": elapsed_ms,
                    "outcome": "error",
                    "error": str(ex),
                },
            )
            raise


@mcp.tool
async def ask(question: str) -> dict:
    """Natural language question -> generated SQL -> executed via the same guard."""
    start = time.perf_counter()
    with tracer.start_as_current_span("ask") as span:
        span.set_attribute("mcp.tool", "ask")
        span.set_attribute("mcp.question", question)

        schema = await _cached_schema()
        sql, reasoning = await nl2sql.to_sql(question, schema)
        span.set_attribute("db.statement", sql)
        span.set_attribute("mcp.reasoning", reasoning)

        try:
            check(sql)
            rows = await upstream.execute_sql(_with_limit(sql, max_rows()))
            elapsed_ms = (time.perf_counter() - start) * 1000
            span.set_attribute("mcp.row_count", len(rows))
            log.info(
                "tool_call",
                extra={
                    "tool": "ask",
                    "sql": sql,
                    "row_count": len(rows),
                    "elapsed_ms": elapsed_ms,
                    "outcome": "ok",
                },
            )
            return {"sql": sql, "rows": rows, "reasoning": reasoning}
        except Exception as ex:
            elapsed_ms = (time.perf_counter() - start) * 1000
            outcome = "blocked" if isinstance(ex, ValueError) else "error"
            log.info(
                "tool_call",
                extra={
                    "tool": "ask",
                    "sql": sql,
                    "elapsed_ms": elapsed_ms,
                    "outcome": outcome,
                    "error": str(ex),
                },
            )
            # sql is present even when execution fails (AC3).
            return {"sql": sql, "error": str(ex), "reasoning": reasoning}


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
