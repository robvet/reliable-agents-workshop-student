# Future Enhancement: Storm Threat Tracking

## What it is

Real-time "which assets are currently threatened by an active storm" tracking

- distinct from a confirmed outage. An asset can be threatened with no outage
  yet, or have an outage after the threat has cleared. Originally designed
  during the events/outages schema refactor (`specs/09-12-Database-Agent-Refactor.md`,
  "Step 9 - Storm threat tracking"), grounded in the app's existing simulated-
  storm map interaction (a draggable storm polygon on the Asset Map).

## What it does

Lets an agent answer "which assets are near the storm right now" as a plain
read, and (noted as a later capability, not built) supports crew pre-staging
by joining current threats with crew availability/region before an outage
even happens.

## How it'd work

- **`event_asset_threat`** - append-only link table (never mutate a row's
  meaning in place): `threat_id` (surrogate PK - lets the same asset be
  threatened, cleared, and re-threatened by the same storm as its polygon is
  dragged back and forth), `event_id` (FK -> events), `asset_id` (FK ->
  grid_assets), `detected_at`, `cleared_at` (NULL = still currently
  threatened).
- **`event_current_threats`** - a view deriving the live threat set:
  `SELECT event_id, asset_id, detected_at FROM event_asset_threat WHERE
cleared_at IS NULL`.
- **Rejected alternative:** a `storm_threat` boolean flag directly on
  `grid_assets`. Same failure mode as the old `outages.status` cache before
  last night's refactor - a flag can't represent "threatened by which
  storm," can't handle overlapping storms, and something has to reliably
  flip it back to `false` when the storm moves away.
- **Write path (planned, not built):** not agent/NL-routed - a deterministic
  map interaction, same category as outage CRUD. On storm-toggle-on: create
  the `events` row (already `EventAgent`'s planned "declare a new event"
  responsibility). On drag-end (throttled, not per mouse-move): sync the
  link table - insert rows for newly-threatened assets, set `cleared_at =
now()` for assets no longer in the current polygon. Planned as a new
  `StormThreatService` (business logic only) -> tool (owns the session/ORM)
  -> Postgres, same boundary as `OutageLifecycleService`.

## How we'd implement it

Everything above is already fully spec'd in `specs/09-12-Database-Agent-Refactor.md`
(Step 9). The schema exists (`event_asset_threat` table + `event_current_threats`
view are already created by the DDL). What's missing is only the write path:
`StormThreatService`, the tool layer beneath it, and wiring the Asset Map's
storm-drag interaction to call it on drag-end.

## Business Value

Pre-outage situational awareness - lets an operator or a future agent see
which assets are at risk before anything actually fails, and (later) enables
proactive crew pre-staging near assets a storm is approaching, rather than
only reacting once an outage is confirmed.

## Risks/Constraints

- **Status: dormant, not dead.** The table/view exist in the DDL today but
  nothing in the app ever writes to `event_asset_threat` - confirmed empirically
  (no ORM model file for it, no service/agent code references it outside the
  NL2SQL prompt telling the model _not_ to use it for status questions).
  This is intentional per the original design - it was Step 9 of a 9-step
  plan, and only steps 1-3 were ever implemented.
- Keeping it dormant (rather than dropping) means the schema still contains
  a table with a one-line DDL comment flagging it as dormant, pointing back
  to this doc - so it doesn't quietly become a mystery to someone reading
  the schema cold later.

## Discussion (notes)

If this is ever picked back up, the storm-drag interaction on the Asset Map
(`simulatedStormActive`, the draggable storm polygon in `app.js`) is the
natural trigger point already built and waiting for a backend to call.
