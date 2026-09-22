# Asset Map: Add Fixed Graph Traversal Queries for Outages

**\*\*\*** Include Meters
go meters to service_locations to get lat/long for meters

## What it is

A map feature: click a transformer - especially one with an active outage -
and see which meters/service locations go dark. Directly serves outage
detection/management/restoration, not customer/billing plumbing.

## What it does

Given an asset (any level - substation, feeder, or transformer), shows the
meters downstream of it. Most useful when that asset has an active outage:
"here's who's affected."

**Interaction idea (2026-09-20):** on the Asset Map, in "Show Outages" mode,
clicking a marker involved in an outage toggles the downstream meters on/off
as their own markers - a distinct color, with a capital **M** inside (same
symbol convention as the existing S/F/T substation/feeder/transformer
markers). Click again to hide them.

## How it'd work

The gap: there's no direct link between `outages` and `service_locations`/
`meters` today. The path is `outages.asset_id -> grid_assets.parent_asset`
(walking down to `TRANSFORMER` if the outaged asset is a feeder/substation)
`-> service_locations.transformer_id -> meters.location_id`. That's a
hierarchy walk, awkward for a map click handler and awkward for an NL2SQL
model to get right reliably.

**Simplification already added (see DDL):** `asset_meter_map`, a view that
pre-joins the whole chain once - `substation_id`, `feeder_id`,
`transformer_id`, `location_id`, `meter_id` - one row per meter. Turns the
query into one flat WHERE clause regardless of which hierarchy level the
outaged asset is at:

```sql
SELECT meter_id FROM asset_meter_map
WHERE substation_id = :asset_id OR feeder_id = :asset_id OR transformer_id = :asset_id;
```

No recursive CTE, no parent-walk logic required from whatever queries it.

## How we'd implement it

The view exists now (added ahead of the feature so the idea/design isn't
lost). Still needed: a backend endpoint (deterministic, not agent/NL-routed

- a map click is the same category as existing outage CRUD) that queries
  `asset_meter_map` for a given asset_id, and a frontend handler on the Asset
  Map to show the result (e.g. highlight/list affected meters when a
  transformer marker is clicked).

**Meter geo-location:** meters don't carry their own lat/long - the path is
`asset_meter_map.location_id -> service_locations.latitude/longitude`. The
endpoint's query needs that join too (`asset_meter_map` doesn't currently
expose lat/long directly, only `location_id`/`meter_id`).

**Reuse note:** `AssetAgent` already has a deterministic (non-NL2SQL)
downstream-assets query built for the chat/Command Center path (see
`docs-keep/business-rules/fixed-graph-traversal-query-for-assets.md`), using
this same `asset_meter_map` view via `run_sql()`. The map endpoint would be a
similar fixed query, adapted to also select `service_locations` lat/long and
scoped as its own small map-specific service method - not a shared function
with `AssetAgent`, since the two surfaces (chat answer vs. map markers) want
different output shapes.

Frontend: toggle state per clicked asset (similar to the existing
`showOutagesOnly` toggle pattern), add/remove meter markers on click without
re-fetching the whole map, new marker icon (`sym-meter`, capital M, distinct
color from S/F/T).

## Business Value

Turns "this transformer is down" into "these N customers/locations are
affected" at a glance - the kind of outage-impact visibility an operator
actually wants, without needing the full customer domain (which this app
intentionally doesn't have) to get it.

## Risks/Constraints

- **Status: view only, not wired to any feature yet.** `asset_meter_map` is
  a pure `CREATE VIEW` - no new table, no write path, no generator changes,
  fully derived from `grid_assets`/`service_locations`/`meters`. Safe to
  have sitting unused until the map feature is actually built.
- Also update `nl2sql.system.txt` to point at this view instead of teaching
  the parent-asset traversal directly, if/when NL2SQL questions about
  "affected meters" become common enough to warrant it.

## Discussion (notes)

Came out of reviewing the schema diagram end-to-end and noticing the
outages <-> service_locations gap explicitly, rather than leaving it as an
implicit "we'll figure it out later" hole.
