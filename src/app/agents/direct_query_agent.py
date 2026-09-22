import logging

from ..models.agent_request import AgentRequest
from ..models.agent_result import AgentResult
from ..models.trace_step import TraceStep
from ..tools.i_mcp_client import IMcpClient
from .base_domain_agent import BaseDomainAgent


class DirectQueryAgent(BaseDomainAgent):
    """Sends the user's direct lookup question to the NL-2-SQL MCP endpoint."""

    name = "direct_query"
    description = "Answers a direct data question using the user's exact words."

    def __init__(self, mcp_client: IMcpClient) -> None:
        self._mcp = mcp_client

    async def handle(self, request: AgentRequest) -> AgentResult:
        question = request.user_prompt
        logging.info("DirectQueryAgent: question=%s", question)
        payload = await self._mcp.query(question)
        rows = payload.get("rows") or []
        sql = payload.get("sql")
        reasoning = payload.get("reasoning")
        data = {
            "rows": rows,
            "count": len(rows),
            "question": question,
            "sql": sql,
            "reasoning": reasoning,
        }
        return AgentResult(
            agent=self.name,
            data=data,
            trace_step=TraceStep(
                agent=self.name,
                action="direct_query",
                summary=f"answered direct query; {len(rows)} rows found",
                detail={
                    "question": question,
                    "tool": "ask",
                    "sql": sql or "",
                    "reasoning": reasoning or "",
                    "rows": str(len(rows)),
                },
            ),
        )