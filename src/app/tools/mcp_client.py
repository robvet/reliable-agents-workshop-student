"""McpClient: the app-side client for the NL-2-SQL MCP data service."""

import asyncio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .i_mcp_client import IMcpClient


class McpClient(IMcpClient):
    # *********************************************
    # *********  Architectural Insights *************
    # *********************************************
    # Role: the app's outbound adapter to the mcp_sql (PgEdge) service (a separate,
    # independently deployed process). Domain agents depend on IMcpClient, not
    # on this concrete class or the MCP wire protocol - the SDK details stay
    # sealed behind query(). Implements IMcpClient; swap in another backend
    # (Fabric, LangGraph, ...) by implementing the same interface.
    #
    # Lifetime: constructed once in the composition root and shared as an
    # app-lifetime singleton. Safe because it is stateless: the connection URL
    # and timeouts are write-once config, and each query() opens and closes its
    # OWN session as a local. Two concurrent calls never share session state.
    """Calls the MCP server's `ask` tool (natural language -> SQL -> rows)."""

    def __init__(
        self,
        url: str,
        timeout: float,
        connect_timeout: float,
    ) -> None:
        """Store connection config. No network I/O here (sessions open per call)."""
        self._url = url
        self._timeout = timeout
        self._connect_timeout = connect_timeout

    async def query(self, text: str) -> dict:
        """Ask a domain-language question; return the server's {"sql", "rows"} result.

        Opens a fresh Streamable HTTP session for this call, runs the `ask` tool,
        and returns its structured content. Raises on a tool-level error so the
        caller (EventAgent) can degrade gracefully.
        """
        # Timeouts live on the httpx client (connect vs read). We own this client's
        # lifecycle - streamable_http_client does not close a client we pass in.
        for attempt in (1, 2):
            timeout = httpx.Timeout(self._timeout, connect=self._connect_timeout)
            async with httpx.AsyncClient(timeout=timeout) as http_client:
                async with streamable_http_client(self._url, http_client=http_client) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool("ask", {"question": text})

            if result.isError:
                detail = result.content[0].text if result.content else "unknown MCP error"
                if attempt == 1 and self._is_transient_db_connect_error(detail):
                    await asyncio.sleep(0.8)
                    continue
                raise RuntimeError(f"MCP ask failed: {detail}")

            # The server reports SQL failures as a normal {"sql", "error"} dict (not a
            # tool-level error), so isError is False. Treat a present "error" key as a
            # failure too - otherwise a failed query looks like a legitimate empty result.
            payload = result.structuredContent or {}
            if "error" in payload:
                detail = str(payload["error"])
                if attempt == 1 and self._is_transient_db_connect_error(detail):
                    await asyncio.sleep(0.8)
                    continue
                raise RuntimeError(f"MCP ask failed: {detail}")

            return payload

        raise RuntimeError("MCP ask failed: transient database connection error after retry")

    @staticmethod
    def _is_transient_db_connect_error(detail: str) -> bool:
        text = detail.lower()
        return (
            "context deadline exceeded" in text
            or "no database connection configured" in text
            or "unable to ping database" in text
        )

    async def run_sql(self, sql: str) -> list[dict]:
        """Execute a read-only SQL statement through MCP `run_sql`."""
        timeout = httpx.Timeout(self._timeout, connect=self._connect_timeout)
        async with httpx.AsyncClient(timeout=timeout) as http_client:
            async with streamable_http_client(self._url, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool("run_sql", {"query": sql})

        if result.isError:
            detail = result.content[0].text if result.content else "unknown MCP error"
            raise RuntimeError(f"MCP run_sql failed: {detail}")

        # FastMCP wraps non-object tool returns (here: list[dict]) under a
        # "result" key in structuredContent. Accept both shapes.
        payload = result.structuredContent
        if isinstance(payload, dict):
            payload = payload.get("result")
        if not isinstance(payload, list):
            raise RuntimeError(
                f"MCP run_sql returned unexpected payload shape: {type(payload).__name__}"
            )
        return payload
