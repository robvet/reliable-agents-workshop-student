# Synthetic Data

## What it is

Deterministic synthetic data for the app's demo/teaching environment, built
by `SpatialDataGenerator` (`src/app/generator/spatial_data_generator.py`).
Populates the entire spine - grid topology, events, crews, outages - in one
run. Triggered from the Synthetic Data panel ("Generate Synthetic Data" /
"Clear Synthetic Data" buttons), or directly via `POST /generator/generate` /
`POST /generator/clear`.

Deterministic on purpose: seeded (`Faker.seed(42)`, `random.seed(42)`), so
the same parameters always produce the same data - useful for demos and
debugging, not meant to simulate real-world randomness.

## What it creates, in order

Each step writes to tables the previous steps already created (strict
foreign-key-safe order):

1. **Grid topology** - 2 substations (fixed), 5 feeders (fixed, each attached
   to a random substation), and `num_locations // 10` transformers (each
   attached to a random feeder). Coordinates are confined to a Dallas/Fort
   Worth metro bounding box, with each level spreading out from its parent
   within a configured radius.
2. **Events** - one guaranteed `"North Region Storm"` event (severity
   `HIGH`, region `North`) for demo stability, plus 3 more events with one
   deterministic instance of each severity (`LOW`/`MEDIUM`/`HIGH`) so the
   outage-create UI's event picker always has variety.
3. **Crews** - `crew_count` crews, random type
   (`DISTRIBUTION`/`EMERGENCY_RESPONSE`/`METERING`/`TRANSMISSION`) and
   region. Only `EMERGENCY_RESPONSE`/`DISTRIBUTION` crews are eligible for
   outage-restoration assignment (falls back to any crew if none of those
   types exist).
4. **Service locations** - `num_locations` locations, each attached to a
   random transformer.
5. **Meters** - one meter per service location (topology only - kept for a
   future "show meters affected by this outage" map feature; see
   `docs-keep/future-enhancements/outage-affected-meters-map.md`).
6. **Outages** (+ status log + work orders) - four fixed outages, not random
   volume:
   - **Storm cluster** (1 outage): pinned to a NORTH-region transformer and
     the storm event, status `CONFIRMED`, so "assets impacted by the storm
     in the north" is coherent.
   - **Baseline cluster** (3 outages): one per severity/status pair -
     `LOW`/`REPORTED`, `MEDIUM`/`CONFIRMED`, `HIGH`/`CREW_ASSIGNED` - each
     attached to a seeded event matching that severity when one exists,
     otherwise its own standalone one-row event.

   Each outage gets an `outage_status_log` entry for its fixed status, and a
   `work_orders` row with an assigned crew - **only crews currently
   `AVAILABLE`** are picked (marked `DISPATCHED` on assignment). The asset's
   own `status` column mirrors the outage's status the same way live
   transitions do (see
   `docs-keep/business-rules/asset-status-business-rules.md`).

## What it does NOT create

`customers`, `outage_reports`, `meter_readings` do not exist in this schema

- removed deliberately. This app is an internal operations tool (asset
  detection, outage management, restoration), and customer data structurally
  belongs in a separate system, not co-located here. See the DDL header
  comment in `src/app/data/ddl/reliableagents_db.sql` and
  `docs-keep/future-enhancements/analytics-asssets-&-outages.md` for the full
  reasoning.

## Parameters and defaults

| Parameter       | Default | What it controls                    |
| --------------- | ------- | ----------------------------------- |
| `num_locations` | 100     | Service locations and meters (1:1). |
| `crew_count`    | 20      | Crew records.                       |

Topology (2 substations, 4 feeders, 20 transformers) and outages (1 storm +
3 baseline, fixed severities/statuses) are no longer parameterized - they're
fixed constants in `spatial_data_generator.py`, small and predictable enough
that a demo/workshop run doesn't need to tune them.

Defaults were deliberately kept small (`num_locations` lowered from 500 to 100) - the point of this app is demonstrating deterministic multi-agent
control patterns, not a large-volume data store.

## How to regenerate

**Regenerate** ("Generate Synthetic Data" button, or `POST
/generator/generate?confirm=true`) truncates every table this generator
owns (`GENERATED_TABLES`, FK-safe order) and repopulates from scratch.
**Clear** ("Clear Synthetic Data" / `POST /generator/clear`) truncates
without repopulating. Both require confirmation - generating replaces all
existing synthetic data, clearing removes it entirely.
