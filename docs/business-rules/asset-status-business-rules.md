# Asset Status Business Rules

## The problem this solves

`grid_assets` used to have one column, `status`, meaning asset lifecycle
(`INSTALLED`/`MAINTENANCE`/`RETIRED`). Whether an asset currently has an open
outage lived somewhere else entirely (`outages` + `outage_status_log`).
Answering "what's the status of this asset" required two separate queries
plus an AI model reliably deciding which fact to lead with — which it did
not do reliably.

## The fix

Split into two clearly-named columns on `grid_assets`, so each question has
exactly one deterministic answer, in one table, no joins, no AI judgment call:

- **`asset_condition`** — lifecycle: `INSTALLED` / `MAINTENANCE` / `RETIRED`.
  Answers "is this asset commissioned and in service?" Unrelated to outages.
- **`status`** — real-time outage state: `REPORTED` / `CONFIRMED` /
  `CREW_ASSIGNED` / `NORMAL`. Answers "does this asset have a problem right
  now, and what stage is it at?" `NORMAL` means the asset is back in service
  - written the moment an outage reaches `RESTORED`, not held back for the
    outage's own later `CLOSED` step.

Both columns are maintained by `OutageLifecycleService` - every outage
create/transition writes to the asset's `status` column, not just to the
outage's own history log.

## Mapping table - every outage event, in full

| Outage event                      | `outage_status_log` gets | `grid_assets.status` gets                                                                                                                                                          |
| --------------------------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `create_outage()`                 | `REPORTED`               | `REPORTED`                                                                                                                                                                         |
| `transition(... "CONFIRMED")`     | `CONFIRMED`              | `CONFIRMED`                                                                                                                                                                        |
| `transition(... "CREW_ASSIGNED")` | `CREW_ASSIGNED`          | `CREW_ASSIGNED`                                                                                                                                                                    |
| `transition(... "RESTORED")`      | `RESTORED`               | `NORMAL` (asset is back in service - no need to wait for CLOSED)                                                                                                                   |
| `transition(... "CLOSED")`        | `CLOSED`                 | `NORMAL` (already NORMAL since RESTORED; CLOSED is the outage's own administrative close, required by the one-open-outage-per-asset guard so the asset can get a new outage later) |

Every one of the 5 outage-lifecycle entry points writes to `grid_assets.status`

- there is no gap where the asset table can fall out of sync with the outage.

## Other tables touched along the way

- **`events`** - only touched by `create_outage()` when no existing event was
  picked (creates a fresh default event row). Not touched by `transition()`.
- **`outages`** - one row per outage, created once. No status column here by
  design - status is derived, never duplicated.
- **`outage_status_log`** - one row per transition, forever (the permanent
  audit trail of when each outage changed state and why).
- **`grid_assets`** - the fast, single-table snapshot described above.
