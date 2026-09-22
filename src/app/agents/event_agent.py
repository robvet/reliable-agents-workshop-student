import logging

from opentelemetry import trace

from ..models.agent_request import AgentRequest
from ..models.agent_result import AgentResult
from ..models.trace_step import TraceStep
from ..tools.i_mcp_client import IMcpClient
from .base_domain_agent import BaseDomainAgent


class EventAgent(BaseDomainAgent):
    """Looks up events (storms/incidents) and their type/severity via the NL-2-SQL MCP endpoint.

    Speaks in domain terms only (event, event type, severity, region). It does not
    know table or column names - the NL-2-SQL layer behind the MCP boundary owns
    the schema and writes the SQL. Outage lookups are OutageAgent's job, not this one's.
    """

    name = "event"
    description = "Looks up events and their type/severity. Needs an asset when scoping events to a specific asset."


    def __init__(self, mcp_client: IMcpClient):
        # inject the MCP client so the agent stays testable and never news up a connection itself
        self._mcp = mcp_client
        self._tracer = trace.get_tracer(__name__)

    async def handle(
            self,
            request: AgentRequest
        ) -> AgentResult:
        # The domain-language QUESTION this agent composed from the entities. This is
        # NOT reasoning - the agent is deterministic; it templates a question, it does
        # not reason. The reasoning belongs to the NL-2-SQL model behind MCP.
        question = self._build_prompt(request)
        with self._tracer.start_as_current_span("event.lookup") as span:
            span.set_attribute("event.question", question)
            logging.info("EventAgent: question=%s", question)
            try:
                payload = await self._mcp.query(question)
            except Exception:
                # Cannot process a step with no data - record the fault and fail the
                # request. The orchestrator turns this into an error event and stops.
                span.set_attribute("event.success", False)
                logging.exception("EventAgent: MCP query failed; failing the step")
                raise

            data = self._parse(payload)
            # Carry the question, the generated SQL, and the NL-2-SQL model's reasoning
            # back on the result and into telemetry (stdout + otel).
            sql = payload.get("sql") if isinstance(payload, dict) else None
            reasoning = payload.get("reasoning") if isinstance(payload, dict) else None
            data["question"] = question
            data["sql"] = sql
            data["reasoning"] = reasoning
            span.set_attribute("event.sql", sql or "")
            span.set_attribute("event.reasoning", reasoning or "")
            span.set_attribute("event.rows", data["count"])
            span.set_attribute("event.success", True)
            logging.info("EventAgent: rows=%d sql=%s", data["count"], sql)
            logging.info("EventAgent: nl2sql_reasoning=%s", reasoning)
            return self._result(
                data=data,
                ok=True,
                summary=f"looked up events ({self._describe(request)}); {data['count']} found",
                detail={
                    "question": question,
                    "tool": "ask",
                    "sql": sql or "",
                    "reasoning": reasoning or "",
                    "rows": str(data["count"]),
                },
            )
    
    # --- helpers -----------------------------------------------------------

    def _build_prompt(
            self, 
            request: AgentRequest
        ) -> str:
        """Domain-language question for the NL-2-SQL agent. No tables, no SQL."""
        e = request.entities
        filters: list[str] = []

        # Scope from the user's extracted entities (region/asset). location is the
        # user's own wording (e.g. "north region"), so append it as-is.
        if e.asset_id:
            filters.append(f"asset {e.asset_id}")
        if e.feeder:
            filters.append(f"feeder {e.feeder}")
        if e.substation:
            filters.append(f"substation {e.substation}")
        if e.event_id:
            filters.append(f"event {e.event_id}")
        if e.location:
            filters.append(f"location {e.location}")

        # Results from prior agents are already appended to request.user_prompt by the
        # ContextBuilder, so this agent does not interpret another agent's data shape.

        question = f"Answer the event portion of this request: {request.user_prompt}"
        if filters:
            question += f" Use these extracted values as required filters: {', '.join(filters)}."
        return question

    def _parse(self, payload) -> dict:
        """Normalize whatever the MCP endpoint returns into a typed shape."""
        if isinstance(payload, list):
            events = payload
        elif isinstance(payload, dict):
            events = payload.get("rows") or payload.get("events") or []
        else:
            events = []
        return {"events": events, "count": len(events)}

    def _describe(self, request: AgentRequest) -> str:
        # Describe scope from typed entities so accumulated prior results do not leak
        # into a user-facing summary string.
        e = request.entities
        scope = {k: v for k, v in e.model_dump().items() if v is not None}
        return ", ".join(f"{k}={v}" for k, v in scope.items()) or "all"

    def _result(self, data: dict, ok: bool, summary: str, detail: dict | None = None) -> AgentResult:
        return AgentResult(
            agent=self.name,
            data=data,
            success=ok,
            trace_step=TraceStep(
                agent=self.name,
                action="lookup_events",
                summary=summary,
                success=ok,
                detail=detail,
            ),
        )


    # def handle(self, request: AgentRequest) -> AgentResult:
    #     return AgentResult(
    #         agent=self.name,
    #         data={"active_events": ["OUT-4471", "OUT-4488"], "status": "in_progress"},
    #         trace_step=TraceStep(
    #             agent=self.name,
    #             action="lookup_events",
    #             summary="(stub) fetched active events",
    #         ),
    #     )
