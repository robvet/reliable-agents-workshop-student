# assets-fixed-graph-traveral-query

## The problem this solves

"What assets are affected by the outage for XFMR-1014?" needs a fixed graph
traversal: asset -> downstream via `grid_assets.parent_asset` -> transformers
-> `service_locations` -> `meters`. That traversal is always the same three
joins - it is not a judgment call. But `AssetAgent` answers it through NL2SQL
(`self._mcp.query()`), asking a model to reconstruct that join from natural
language on every call. In practice the model sometimes performs the join and
sometimes doesn't, so the same question gets a different answer from one run
to the next - confirmed live: multiple identical questions returned only the
named transformer itself, with no downstream assets, despite an explicit
traversal rule already added to `src/mcp_sql/prompts/nl2sql.system.txt`.

A related, separately-fixed symptom: the ReAct loop kept re-calling the asset
agent (up to `MAX_STEPS`) hoping a repeat call would return something new. It
never would - the no-progress guard in `orchestrator.py` compared the entire
`AgentResult.data` dict, including `sql`/`question`/`reasoning`, which are
free-text NL2SQL output that differs on almost every call by construction. That
guard has been fixed separately (excludes those volatile keys from the
comparison). This doc is about the other half: making the traversal itself not
depend on the model at all.

## The fix

Move the traversal out of the model's hands entirely. The schema already has
an unwired view for exactly this shape - `asset_meter_map`
(`src/app/data/ddl/reliableagents_db.sql`), which flattens
substation -> feeder -> transformer -> service_location -> meter into one flat
table (currently ID columns only: `substation_id`, `feeder_id`,
`transformer_id`, `location_id`, `meter_id`).

Add one boolean, `Entities.needs_downstream_assets`, set once per turn by the
intent classifier (the one model call that already runs every turn - no new
model call added). When true, `AssetAgent` makes a second call after its
normal NL2SQL lookup: `self._mcp.run_sql(fixed_sql)` - a hand-written,
hardcoded SQL string built from `asset_meter_map` (joined back to
`grid_assets`/`service_locations`/`meters` for human-readable labels, since the
view alone only carries IDs). `run_sql` executes literal SQL with no model
involved, the same mechanism `MapAssetService` already uses for the Asset Map.

Net effect: exactly one model judgment (the boolean flag, decided once per
turn), and a fixed, identical query every time that flag is true - not a
model re-deciding and re-writing SQL on every call.

## The Technical Implementation

1. `src/app/models/entities.py` - add `needs_downstream_assets: bool = False`.
2. `src/app/prompts/intent_classification.jinja2` - add one rule telling the
   classifier when to set that field true (question asks about assets
   affected, impacted, or downstream of a named asset).
3. `src/app/agents/asset_agent.py` - in `handle()`, after the existing
   `self._mcp.query(prompt)` call: if
   `request.entities.needs_downstream_assets and request.entities.asset_id`,
   build one fixed SQL string against `asset_meter_map` (joined to
   `grid_assets`/`service_locations`/`meters` for names), call
   `self._mcp.run_sql(fixed_sql)`, and add the rows to
   `data["downstream_assets"]` before returning the `AgentResult`.
4. Two MCP calls total per invocation when the flag is true: one NL2SQL `ask`
   (unchanged, existing behavior) and one direct `run_sql` (new, no model).

## Notes & Constraints

- `asset_meter_map` only selects ID columns - the fixed query must join back
  to `grid_assets.asset_name`, `service_locations.address`, and
  `meters.meter_id` (etc.) to produce a human-readable answer, not raw UUIDs.
- This does not remove all model involvement. The classifier's boolean flag is
  still one LLM judgment, made once per turn - a false negative on an odd
  phrasing is possible. What it removes is the model re-deciding (and
  re-writing SQL) at every ReAct step, which is what caused the missing
  downstream data in the first place.
- Implemented: `Entities.needs_downstream_assets`, `AssetAgent._build_downstream_sql()`,
  and the second `run_sql` call are all live in `asset_agent.py`.
