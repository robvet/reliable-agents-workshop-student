# Asset Map: Show Downstream Assets

## Scope

Select a grid asset on the Asset Map and choose **Show Downstream Assets**
in its popup. The dependency footprint includes every downstream level:

| Starting asset | Downstream assets |
| --- | --- |
| Substation | Feeders, transformers, and meters |
| Feeder | Transformers and meters |
| Transformer | Meters |

The selected asset is the starting point, not one of its own descendants.
Service locations provide meter coordinates; they are not separate asset
markers. Counts describe assets and meters, not unique customers.

## Interaction

- The link is available regardless of whether the asset has an outage.
- Only **one starting asset per map** can be expanded at a time. Expanding
  another asset replaces the previous footprint.
- Existing feeder/transformer markers are reused and emphasized, not
  duplicated. Unrelated base assets are dimmed.
- Meters use a distinct purple **M** marker in the normal view, alongside
  the existing S/F/T symbols. Co-located meters share a marker whose popup
  lists every meter.
- **Hide Downstream Assets** removes added markers and restores the base
  map's current outage-filter styling. It does not remove existing grid
  markers.
- Both inline and pop-out map renderers use the same downstream controller.
  The pop-out inherits the outage-view setting when opened, then maintains
  its own selection and filter state.
- Loading, empty results, missing coordinates, and failures are visible
  near the map. Closing an expansion while loading cancels it; switching
  roots cannot apply a stale response.

## Outage-view assumption

When **Show Outages** is active and the starting asset has an active outage:

1. The starting asset stays red.
2. Every displayed downstream asset is also red, **assumed affected by the
   upstream outage**.
3. Downstream popups distinguish that assumption from recorded status.
4. **Hide Downstream Assets** removes the footprint, but the starting asset
   stays red because the outage view remains active.

Red includes recorded outages and assumed downstream impact; the legend
states this explicitly. This is a workshop visualization assumption, not
proof that every downstream asset has independently failed. No outage
records are created and no database statuses are changed.

Turning off the outage view restores normal type colors for the expanded
footprint. A healthy starting asset does not imply a downstream outage.

## Implementation

### Snapshot redesign: backend slice

`GET /map/snapshot` now returns all grid assets and meters in a typed
`MapSnapshotResponse`, using one fixed SQL statement through MCP. Records
include parent IDs, coordinates, recorded statuses, outage flags, and crew
names where applicable. Missing coordinates do not remove records from the
hierarchy. No server-side cache is retained.

The existing `/map/assets` response remains unchanged for its other
consumers. The frontend still uses the downstream endpoint described below;
that endpoint and its contract will be removed when the frontend switches
to local downstream selection.

### Deterministic API

`GET /map/assets/{asset_id}/descendants` returns a validated
`MapDescendantsResponse` containing:

- `source`: the selected grid asset, including its recorded status and
  whether it has an active outage.
- `assets`: distinct downstream feeders, transformers, and meters, with
  IDs, types, parent IDs, recorded statuses, and coordinates when available.
  Meter rows also identify their service location.

An unknown asset returns 404; an invalid identifier returns 422; a failed
lookup returns 502. A valid asset with no descendants returns an empty list.

The route delegates to
[MapAssetService](../../src/app/services/map_asset_service.py), using a
fixed, read-only SQL query through the existing MCP `run_sql` interface.
There is no intent classification, agent invocation, or model-generated SQL.

The fixed-depth query follows `grid_assets.parent_asset` to feeders and
transformers, then `service_locations.transformer_id` and
`meters.location_id` to meters. Meter latitude/longitude come from the
service location. Grid assets without meters remain in the result.

The existing `asset_meter_map` view is still used by the
[chat downstream lookup](../business-rules/fixed-graph-traversal-query-for-assets.md).
It is not the source for this map lookup: its inner joins exclude branches
with no meters. No view, schema, generator, or chat-prompt changes are needed.

### Frontend

[MapDownstreamController](../../src/frontend/map_downstream_controller.js)
owns the single-root selection, bounded lookup, overlay markers, and
combined outage/dependency styling. Both renderers supply their existing
map, base markers, icon renderer, status labels, and API base URL.

## Validation

Run the focused tests from the repository root:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_map_asset_service.py tests/test_map_descendants_routes.py tests/test_asset_agent.py -q
node --test tests/TestMapDownstreamController.cjs
```

Coverage includes typed responses, deduplication, empty results, identifier
validation, SQL construction, malformed responses, API errors, co-located
meters, missing coordinates, root switching, cancellation, and outage-view
color restoration.

Service tests mock MCP responses; API tests mock the service. These unit
tests do not execute SQL against a database. Query correctness across all
three starting levels, unrelated branches, and assets without meters still
requires a live MCP/PostgreSQL integration check in the target environment.

For a browser check, open **Asset Map**, choose **Show Outages**, expand an
outage asset, and verify that its downstream footprint is red. Collapse it
and verify that its parent remains red. Repeat in the normal view and with
the pop-out renderer.
