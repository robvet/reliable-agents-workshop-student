# Asset/Outage Analytics

## What it is

A future phase that scores asset reliability from outage history - e.g.
"which transformers fail most often," restoration-time trends per asset,
SAIDI/SAIFI-style reliability metrics. Not part of the current app; this
doc exists so the idea and the groundwork already found aren't lost while
the app's scope gets narrowed down to its core spine (asset detection,
outage management, restoration).

## What it does

Rolls up existing outage-history data by asset to surface reliability
signal: outage frequency per asset, average/actual restoration duration,
estimated-vs-actual (ETR) accuracy, and crew-effort cost per asset over
time.

## How it'd work

Nothing new needs to be captured - the source of truth already exists:

- **`outage_status_log`** - the append-only transition ledger. `from_status`
  / `to_status` / `event_time` per row already lets you compute actual
  restoration duration (time from `REPORTED` to `RESTORED`) per outage.
  `etr` already supports estimated-vs-actual comparison.
- **`outages`** - roll the above up by `asset_id` to get outage frequency
  and average restoration time per asset over time.
- **`events`** - cause (`event_type_code`) and `severity` context per
  outage.
- **`work_orders`** - `estimated_hours`/`actual_hours` give a crew-effort/
  cost dimension, already joinable via `outage_id`.

## How we'd implement it

Likely just queries/aggregations (a new read-only agent or reporting view)
against the tables above - no new tables, no new columns look obviously
missing. Duration is derivable from existing timestamps; cause/severity
already live on `events`; crew effort already lives on `work_orders`.

Naming: `outage_status_log` was considered for a rename to `outage_history`
(reads more naturally in an analytics context). Decision: don't rename
preemptively - the current name is accurate to what it is today, nothing is
confused by it, and renaming now is effort spent for a hypothetical feature
with no immediate payoff. Revisit only if/when this feature is actually
being built and the name gets in the way.

## Business Value

Gives operators a data-backed way to prioritize maintenance/replacement
spend (assets with high outage frequency or slow restoration times) instead
of relying on anecdote. Standard utility reliability-engineering pattern
(SAIDI/SAIFI), grounded in data the app already collects.

## Risks/Constraints

- **`outage_reports` is dead weight today, not a source for this.** Checked
  against the live schema and the generator: `linked_outage_id` (the one
  column that would make a report meaningful) is hardcoded to `None` for
  every row the generator creates (`spatial_data_generator.py`, STEP 8) -
  confirmed empirically, every seeded row shows `linked_outage_id = [null]`.
  `status` (`NEW`/`LINKED`/`RESOLVED`) is assigned at random, independent of
  whether a link exists. No agent, service, or route reads this table
  anywhere in the app. It was never wired up to mean what its name implies.
- **Dormant-table tradeoff.** Current plan for `customers`/`outage_reports`/
  `meter_readings`: leave the `CREATE TABLE` statements in the DDL as-is (no
  migration, no live-DB schema change, fully reversible), and stop the app
  from actively using them - no generator seeding, no agent/service code
  touching them. They sit empty and dormant rather than being deleted. Watch
  for: an empty, unused table sitting in the schema can still read as "wait,
  what's this for?" to someone new looking at the DDL cold - the same
  category of confusion as the `status` naming collision from the
  asset/outage refactor, just smaller in scale. If this path is taken, add a
  one-line comment in the DDL flagging these as dormant/reserved so it
  doesn't quietly become a mystery later.

## Discussion (notes)

Possible corroboration idea, not scoped, not decided: if `outage_reports`
were ever revived for real, customer-reported outages could serve as a
corroborating signal for outage detection (e.g., "3 reports near this
transformer" reinforcing or preceding a confirmed AMI/SCADA detection) - a
standard OMS pattern. Noted here only so the idea isn't lost.
