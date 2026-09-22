from abc import ABC, abstractmethod


class IMcpClient(ABC):
    """The app's contract for a data-access backend reached via MCP.

    The swap-your-own-backend extension point: McpClient (PgEdge) ships with the
    harness; a customer plugs in Fabric, LangGraph, or any other backend by
    implementing this interface. Domain agents and services depend on THIS
    interface, not on any concrete backend's SDK.
    """

    @abstractmethod
    async def query(self, text: str) -> dict:
        """Ask a domain-language question; return the backend's {"sql", "rows"} result."""

    @abstractmethod
    async def run_sql(self, sql: str) -> list[dict]:
        """Execute a read-only SQL statement; return the resulting rows."""
