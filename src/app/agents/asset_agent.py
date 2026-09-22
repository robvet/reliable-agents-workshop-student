import logging

from ..models.agent_request import AgentRequest
from ..models.agent_result import AgentResult
from ..models.trace_step import TraceStep
from ..tools.i_mcp_client import IMcpClient
from .base_domain_agent import BaseDomainAgent


class AssetAgent(BaseDomainAgent):
    """Resolves grid assets and their topology via the NL-2-SQL MCP endpoint.

    Speaks in domain terms only (assets, transformers, feeders, substations,
    topology, region). It does not know table or column names - the NL-2-SQL
    layer behind the MCP boundary owns the schema and writes the SQL.
    """

    name = "asset"
    description = "Resolves grid assets (transformers, feeders, substations) and their topology/paths."

    def __init__(self, mcp_client: IMcpClient):
        # inject the MCP client so the agent stays testable and never news up a connection itself
        self._mcp = mcp_client

    async def handle(self, request: AgentRequest) -> AgentResult:
        # Constructs a domain-language question for the NL-2-SQL agent.
        prompt = self._build_prompt(request)

        # Log the domain question sent to the NL-2-SQL MCP server.
        logging.info("AssetAgent: reasoning (question)=%s", prompt)

        # Calls the MCP NL-2-SQL endpoint 
        try:
            payload = await self._mcp.query(prompt)
        except Exception:
            # Cannot process a step with no data - record the fault and fail the
            # request. The orchestrator turns this into an error event and stops.
            logging.exception("AssetAgent: MCP query failed; failing the step")
            raise

        data = self._parse(payload)
        # Surface the generated SQL and the question on the result so they travel
        # back with the agent's output (and are visible to operators).
        sql = payload.get("sql") if isinstance(payload, dict) else None
        reasoning = payload.get("reasoning") if isinstance(payload, dict) else None
        data["sql"] = sql
        data["question"] = prompt
        data["reasoning"] = reasoning
        logging.info("AssetAgent: rows=%d sql=%s", data["count"], sql)

        # Deterministic second call - not NL2SQL. The classifier already decided
        # (once, per turn) that this question needs downstream assets; the join
        # itself is fixed, hand-written SQL, never model-generated, so it returns
        # the same result every time for the same asset. See
        # docs/business-rules/fixed-graph-traversal-query-for-assets.md.
        if request.entities.needs_downstream_assets and request.entities.asset_id:
            try:
                downstream_sql = self._build_downstream_sql(request.entities.asset_id)
                downstream_rows = await self._mcp.run_sql(downstream_sql)
            except Exception:
                logging.exception("AssetAgent: downstream assets run_sql failed")
                downstream_rows = []
            data["downstream_assets"] = downstream_rows
            logging.info("AssetAgent: downstream_assets rows=%d", len(downstream_rows))

        return self._result(
            data=data,
            ok=True,
            summary=f"resolved assets ({self._describe(request)}); {data['count']} found",
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

        # Scope from the user's extracted entities (asset/feeder/substation/location).
        if e.asset_id:
            filters.append(f"asset {e.asset_id}")
        if e.feeder:
            filters.append(f"feeder {e.feeder}")
        if e.substation:
            filters.append(f"substation {e.substation}")
        if e.location:
            filters.append(f"location {e.location}")

        question = f"Answer the asset portion of this request: {request.user_prompt}"
        if filters:
            question += (
                f" Scope the query starting from: {', '.join(filters)}. If the request asks "
                "about assets affected, impacted, or downstream of that starting point (e.g. "
                "due to an outage), that starting asset is the ROOT of the traversal, not an "
                "exact-match filter - include it and everything downstream of it. Only treat "
                "it as an exact-match filter (return just that one asset) when the request is "
                "asking about the asset itself with no affected/impacted/downstream framing."
            )

        # Static schema reference: lets a question about the ALLOWED/POSSIBLE values of
        # a column ("what status values CAN an asset show") be answered directly, instead
        # of being misread as a request for what the live data currently contains.
        question += (
            " Reference (fixed schema, not live data): grid_assets.asset_type allows "
            "SUBSTATION, FEEDER, TRANSFORMER; grid_assets.asset_condition (lifecycle - is the "
            "asset commissioned and in service?) allows INSTALLED, MAINTENANCE, RETIRED; "
            "grid_assets.status (real-time outage state, kept in sync automatically) allows "
            "REPORTED, CONFIRMED, CREW_ASSIGNED, RESTORED, NORMAL - NORMAL means no open "
            "outage. If the question asks what values a column CAN or MAY hold, answer from "
            "this reference instead of querying current rows."
        )
        return question

    def _build_downstream_sql(self, asset_name: str) -> str:
        """Fixed, hand-written SQL - never model-generated. Uses asset_meter_map
        (substation -> feeder -> transformer -> service_location -> meter,
        already defined in the DDL) joined back to grid_assets/service_locations/
        meters for human-readable labels, since the view alone only carries IDs.
        Matches asset_name at any level, since the named asset could itself be a
        substation, feeder, or transformer.
        """
        safe_name = asset_name.replace("'", "''")
        return (
            "SELECT sub.asset_name AS substation_name, "
            "feeder.asset_name AS feeder_name, "
            "xfmr.asset_name AS transformer_name, "
            "sl.address, sl.location_id, m.meter_id "
            "FROM asset_meter_map amm "
            "JOIN grid_assets sub ON sub.asset_id = amm.substation_id "
            "JOIN grid_assets feeder ON feeder.asset_id = amm.feeder_id "
            "JOIN grid_assets xfmr ON xfmr.asset_id = amm.transformer_id "
            "JOIN service_locations sl ON sl.location_id = amm.location_id "
            "JOIN meters m ON m.meter_id = amm.meter_id "
            f"WHERE sub.asset_name ILIKE '{safe_name}' "
            f"OR feeder.asset_name ILIKE '{safe_name}' "
            f"OR xfmr.asset_name ILIKE '{safe_name}'"
        )

    def _parse(self, payload) -> dict:
        """Normalize whatever the MCP endpoint returns into a typed shape."""
        if isinstance(payload, list):
            assets = payload
        elif isinstance(payload, dict):
            assets = payload.get("rows") or payload.get("assets") or []
        else:
            assets = []
        return {"assets": assets, "count": len(assets)}

    def _describe(self, request: AgentRequest) -> str:
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
                action="resolve_asset",
                summary=summary,
                success=ok,
                detail=detail,
            ),
        )
