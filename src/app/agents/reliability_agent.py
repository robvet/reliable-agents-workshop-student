import logging

from ..models.agent_request import AgentRequest
from ..models.agent_result import AgentResult
from ..models.trace_step import TraceStep
from ..tools.i_mcp_client import IMcpClient
from .base_domain_agent import BaseDomainAgent


class ReliabilityAgent(BaseDomainAgent):
    """Answers reliability questions via the NL-2-SQL MCP endpoint."""

    name = "reliability"
    description = "Answers reliability, failure-history, and maintenance questions for assets."

    def __init__(self, mcp_client: IMcpClient):
        # inject the MCP client so the agent stays testable and never news up a connection itself
        self._mcp = mcp_client

    async def handle(self, request: AgentRequest) -> AgentResult:
        prompt = self._build_prompt(request)
        # The composed question IS this deterministic agent's "reasoning" - what it
        # decided to ask, and why (which entity scope it applied).
        logging.info("ReliabilityAgent: reasoning (question)=%s", prompt)
        try:
            payload = await self._mcp.query(prompt)
        except Exception:
            # Cannot process a step with no data - record the fault and fail the
            # request. The orchestrator turns this into an error event and stops.
            logging.exception("ReliabilityAgent: MCP query failed; failing the step")
            raise

        data = self._parse(payload)
        # Surface the generated SQL and the question on the result so they travel
        # back with the agent's output (and are visible to operators).
        sql = payload.get("sql") if isinstance(payload, dict) else None
        reasoning = payload.get("reasoning") if isinstance(payload, dict) else None
        data["sql"] = sql
        data["question"] = prompt
        data["reasoning"] = reasoning
        logging.info("ReliabilityAgent: rows=%d sql=%s", data["count"], sql)
        return self._result(
            data=data,
            ok=True,
            summary=f"looked up reliability ({self._describe(request)}); {data['count']} found",
            detail={
                "question": prompt,
                "tool": "ask",
                "sql": sql or "",
                "reasoning": reasoning or "",
                "rows": str(data["count"]),
            },
        )

    # --- helpers -----------------------------------------------------------

    def _build_prompt(self, request: AgentRequest) -> str:
        """Domain-language question for the NL-2-SQL agent. No tables, no SQL."""
        e = request.entities
        filters: list[str] = []

        # Scope from the user's extracted entities (asset/event/location).
        if e.asset_id:
            filters.append(f"asset {e.asset_id}")
        if e.feeder:
            filters.append(f"feeder {e.feeder}")
        if e.substation:
            filters.append(f"substation {e.substation}")
        if e.event_id:
            filters.append(f"outage {e.event_id}")
        if e.location:
            filters.append(f"location {e.location}")

        # Results from prior agents are already appended to request.user_prompt by the
        # ContextBuilder, so this agent does not interpret another agent's data shape.
        question = f"Answer the reliability portion of this request: {request.user_prompt}"
        if filters:
            question += f" Use these extracted values as required filters: {', '.join(filters)}."
        return question

    def _parse(self, payload) -> dict:
        """Normalize whatever the MCP endpoint returns into a typed shape."""
        if isinstance(payload, list):
            reliability = payload
        elif isinstance(payload, dict):
            reliability = payload.get("rows") or payload.get("reliability") or []
        else:
            reliability = []
        return {"reliability": reliability, "count": len(reliability)}

    def _describe(self, request: AgentRequest) -> str:
        e = request.entities
        scope = {key: value for key, value in e.model_dump().items() if value is not None}
        return ", ".join(f"{key}={value}" for key, value in scope.items()) or "all"

    def _result(self, data: dict, ok: bool, summary: str, detail: dict | None = None) -> AgentResult:
        return AgentResult(
            agent=self.name,
            data=data,
            success=ok,
            trace_step=TraceStep(
                agent=self.name,
                action="assess_reliability",
                summary=summary,
                success=ok,
                detail=detail,
            ),
        )
