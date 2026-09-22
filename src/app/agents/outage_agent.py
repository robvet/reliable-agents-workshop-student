import logging
from typing import Optional

from opentelemetry import trace

from ..models.agent_request import AgentRequest
from ..models.agent_result import AgentResult
from ..models.trace_step import TraceStep
from ..tools.i_mcp_client import IMcpClient
from ..data import Outage
from ..services.outage_lifecycle_service import OutageLifecycleService
from ..services.llm_outage_note_classifier import LlmOutageNoteClassifier
from ..skills.skill_repository import SkillRepository
from .base_domain_agent import BaseDomainAgent


class OutageAgent(BaseDomainAgent):
    """Looks up outages via NL-2-SQL, and is the single entry point for outage writes.

    Speaks in domain terms only (outage, status, impact, asset). It does not
    know table or column names - the NL-2-SQL layer behind the MCP boundary owns
    the schema and writes the SQL. Current status comes from `outage_current_status`,
    not a column on `outages` - the model is told this via the NL-2-SQL system prompt.

    Retrieval goes through MCP/NL-2-SQL (handle()). Deterministic writes
    (create_outage/transition/list_outages) forward directly to
    `OutageLifecycleService` - no reasoning, no MCP - so both the natural-language
    path and the deterministic `/outages` REST path go through this one agent.
    """

    name = "outage"
    description = "Looks up outages and their status/impact. Needs an asset or event when scoping to one."

    def __init__(
        self,
        mcp_client: IMcpClient,
        outage_lifecycle_service: Optional[OutageLifecycleService] = None,
        llm_outage_note_classifier: Optional[LlmOutageNoteClassifier] = None,
    ):
        # inject the MCP client so the agent stays testable and never news up a connection itself
        self._mcp = mcp_client
        self._outage_lifecycle_service = outage_lifecycle_service
        self._llm_outage_note_classifier = llm_outage_note_classifier
        self._tracer = trace.get_tracer(__name__)

    # --- deterministic writes (no reasoning, no MCP) ------------------------
    # Thin forwarding to OutageLifecycleService. This agent is the single entry
    # point for outage traffic; the deterministic REST path calls these methods
    # instead of the service directly.

    def create_outage(
        self,
        asset_id: str,
        event_id: Optional[str] = None,
        impact_count: Optional[int] = None,
        impact_magnitude: Optional[float] = None,
    ) -> Outage:
        if self._outage_lifecycle_service is None:
            raise RuntimeError("Outage management is not configured (DATABASE_URL is not set).")
        return self._outage_lifecycle_service.create_outage(
            asset_id=asset_id,
            event_id=event_id,
            impact_count=impact_count,
            impact_magnitude=impact_magnitude,
        )

    async def transition(
        self,
        outage_id: str,
        to_status: str,
        note: Optional[str] = None,
        crew_id: Optional[str] = None,
    ) -> Outage:
        if self._outage_lifecycle_service is None:
            raise RuntimeError("Outage management is not configured (DATABASE_URL is not set).")
        outage = self._outage_lifecycle_service.transition(
            outage_id=outage_id,
            to_status=to_status,
            note=note,
            crew_id=crew_id,
        )

        # Note-triage: only runs when a note was actually typed and the classifier
        # is configured. Model proposes a recommendation; this method independently
        # checks it against the skill's own hazard_keywords before writing anything -
        # the model's opinion alone is never enough to escalate a HIGH severity.
        if note and self._llm_outage_note_classifier is not None:
            try:
                result = await self._llm_outage_note_classifier.classify(note)
                front_matter, _ = SkillRepository.get("outage_note_triage")
                hazard_keywords = front_matter.get("hazard_keywords", [])
                note_lower = note.lower()
                hazard_present = any(kw.lower() in note_lower for kw in hazard_keywords)
                if result.escalate and (result.severity != "HIGH" or hazard_present):
                    self._outage_lifecycle_service.update_event_severity(
                        event_id=outage.event_id,
                        severity=result.severity,
                    )
                    logging.info(
                        "OutageAgent.transition: note-triage escalated event_id=%s to %s (%s)",
                        outage.event_id, result.severity, result.reasoning,
                    )
                elif result.escalate:
                    logging.info(
                        "OutageAgent.transition: note-triage recommended HIGH but no hazard "
                        "keyword present in note; rejected. outage_id=%s", outage_id,
                    )
            except Exception:
                # Note-triage is a best-effort enhancement, not part of the status
                # transition's own contract - a classifier failure must never fail
                # the transition itself.
                logging.exception("OutageAgent.transition: note-triage failed; transition still applied")

        return outage

    def list_outages(self) -> list[dict]:
        if self._outage_lifecycle_service is None:
            raise RuntimeError("Outage management is not configured (DATABASE_URL is not set).")
        return self._outage_lifecycle_service.list_outages()

    def list_crews(self) -> list[dict]:
        if self._outage_lifecycle_service is None:
            raise RuntimeError("Outage management is not configured (DATABASE_URL is not set).")
        return self._outage_lifecycle_service.list_crews()

    async def handle(
            self,
            request: AgentRequest
        ) -> AgentResult:
        # The domain-language QUESTION this agent composed from the entities. This is
        # NOT reasoning - the agent is deterministic; it templates a question, it does
        # not reason. The reasoning belongs to the NL-2-SQL model behind MCP.
        question = self._build_prompt(request)
        with self._tracer.start_as_current_span("outage.lookup") as span:
            span.set_attribute("outage.question", question)
            logging.info("OutageAgent: question=%s", question)
            try:
                payload = await self._mcp.query(question)
            except Exception:
                # Cannot process a step with no data - record the fault and fail the
                # request. The orchestrator turns this into an error event and stops.
                span.set_attribute("outage.success", False)
                logging.exception("OutageAgent: MCP query failed; failing the step")
                raise

            data = self._parse(payload)
            # Carry the question, the generated SQL, and the NL-2-SQL model's reasoning
            # back on the result and into telemetry (stdout + otel).
            sql = payload.get("sql") if isinstance(payload, dict) else None
            reasoning = payload.get("reasoning") if isinstance(payload, dict) else None
            data["question"] = question
            data["sql"] = sql
            data["reasoning"] = reasoning
            span.set_attribute("outage.sql", sql or "")
            span.set_attribute("outage.reasoning", reasoning or "")
            span.set_attribute("outage.rows", data["count"])
            span.set_attribute("outage.success", True)
            logging.info("OutageAgent: rows=%d sql=%s", data["count"], sql)
            logging.info("OutageAgent: nl2sql_reasoning=%s", reasoning)
            return self._result(
                data=data,
                ok=True,
                summary=f"looked up outages ({self._describe(request)}); {data['count']} found",
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

        question = f"Answer the outage portion of this request: {request.user_prompt}"
        if filters:
            question += f" Use these extracted values as required filters: {', '.join(filters)}."
        return question

    def _parse(self, payload) -> dict:
        """Normalize whatever the MCP endpoint returns into a typed shape."""
        if isinstance(payload, list):
            outages = payload
        elif isinstance(payload, dict):
            outages = payload.get("rows") or payload.get("outages") or []
        else:
            outages = []
        return {"outages": outages, "count": len(outages)}

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
                action="lookup_outages",
                summary=summary,
                success=ok,
                detail=detail,
            ),
        )
