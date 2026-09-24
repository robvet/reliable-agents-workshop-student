import logging

from ..models.agent_request import AgentRequest
from ..models.agent_result import AgentResult
from ..models.trace_step import TraceStep
from ..tools.i_mcp_client import IMcpClient
from .base_domain_agent import BaseDomainAgent


class AssetAgent(BaseDomainAgent):
    """Resolves grid assets and their topology via the NL-2-SQL MCP endpoint.

    The model-generated read path speaks in domain terms (assets, transformers,
    feeders, substations, topology, region). The NL-2-SQL layer behind the MCP
    boundary maps that question to the database and writes the SQL. A separate
    fixed-SQL branch handles deterministic downstream traversal.
    """

    name = "asset"
    description = "Resolves grid assets (transformers, feeders, substations) and their topology/paths."

    def __init__(self, mcp_client: IMcpClient):
        # Depend on the interface supplied by the composition root. The agent
        # never constructs a concrete client or opens its own data connection.
        self._mcp = mcp_client

    async def handle(self, request: AgentRequest) -> AgentResult:
        # Build a domain-language question from the typed request. AssetAgent
        # describes the data it needs; the MCP service decides how to query it.
        prompt = self._build_prompt(request)

        # Record the exact question crossing the MCP boundary for observability.
        logging.info("AssetAgent: reasoning (question)=%s", prompt)

        # Ask the injected MCP client to resolve the domain question. The client
        # calls the NL-2-SQL service and returns its structured payload.
        try:
            payload = await self._mcp.query(prompt)
        except Exception:
            # Do not turn a tool failure into a successful empty result. Record
            # the fault and re-raise it so the orchestrator stops this request.
            logging.exception("AssetAgent: MCP query failed; failing the step")
            raise

        # Normalize the successful MCP payload into the stable asset data shape
        # expected by the rest of the typed pipeline.
        data = self._parse(payload)

        # Preserve the question, generated SQL, and server reasoning as evidence.
        # These fields travel with the result and make the data leg inspectable.
        sql = payload.get("sql") if isinstance(payload, dict) else None
        reasoning = payload.get("reasoning") if isinstance(payload, dict) else None
        data["sql"] = sql
        data["question"] = prompt
        data["reasoning"] = reasoning
        logging.info("AssetAgent: rows=%d sql=%s", data["count"], sql)

        # Run the provided deterministic traversal only when the classifier set
        # the typed flag and supplied a starting asset. This second call does not
        # use NL-2-SQL: the fixed join returns the same topology for the same data.
        # See
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

        # Return a validated AgentResult rather than prose. The trace step carries
        # a concise summary and the evidence operators need to inspect this hop.
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
        """Build the domain-language question sent to the NL-2-SQL service."""
        # Read only the typed entity slots relevant to the asset domain.
        e = request.entities
        filters: list[str] = []

        # Translate each populated entity into a domain label. These values scope
        # the question without asking AssetAgent to generate SQL.
        if e.asset_id:
            filters.append(f"asset {e.asset_id}")
        if e.feeder:
            filters.append(f"feeder {e.feeder}")
        if e.substation:
            filters.append(f"substation {e.substation}")
        if e.location:
            filters.append(f"location {e.location}")

        # Preserve the user's complete wording so constraints that are not entity
        # slots, such as time ranges, counts, and exclusions, are not discarded.
        question = f"Answer the asset portion of this request: {request.user_prompt}"

        # Add the typed starting scope when present. The traversal guidance keeps
        # an affected-assets request from becoming an incorrect exact-match query.
        if filters:
            question += (
                f" Scope the query starting from: {', '.join(filters)}. If the request asks "
                "about assets affected, impacted, or downstream of that starting point (e.g. "
                "due to an outage), that starting asset is the ROOT of the traversal, not an "
                "exact-match filter - include it and everything downstream of it. Only treat "
                "it as an exact-match filter (return just that one asset) when the request is "
                "asking about the asset itself with no affected/impacted/downstream framing."
            )

        # Append the fixed domain reference for questions about allowed values.
        # This distinguishes schema possibilities from values in the current rows.
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
        """Build the fixed downstream traversal query.

        This query is never model-generated. It walks the hierarchy from
        substation to feeder, transformer, service location, and meter, and
        matches the starting asset at every supported asset level.
        """
        # Escape a quote in the classifier-provided asset name before placing it
        # in the fixed query's string literals.
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
        """Normalize a successful MCP payload into the agent's stable data shape."""
        # Accept the supported successful response shapes: rows returned directly
        # as a list, or rows nested under a known dictionary key.
        if isinstance(payload, list):
            assets = payload
        elif isinstance(payload, dict):
            assets = payload.get("rows") or payload.get("assets") or []
        else:
            assets = []
        return {"assets": assets, "count": len(assets)}

    def _describe(self, request: AgentRequest) -> str:
        # Summarize populated entity slots for the human-readable trace message.
        e = request.entities
        scope = {k: v for k, v in e.model_dump().items() if v is not None}
        return ", ".join(f"{k}={v}" for k, v in scope.items()) or "all"

    def _result(self, data: dict, ok: bool, summary: str, detail: dict | None = None) -> AgentResult:
        # Construct the validated agent contract and its matching trace entry in
        # one place so every AssetAgent result has the same observable shape.
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
