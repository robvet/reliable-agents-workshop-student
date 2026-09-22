---
min_impact_count_for_major: 500
---

# Event Severity Classification

Judge each event's severity (LOW / MEDIUM / HIGH) from what actually happened, never
from `event_type_code`. Type says what happened (STORM, VEHICLE, FIRE, ...); severity
says how bad this particular instance was, and those are independent facts. An EF1
tornado and an EF5 tornado are both `event_type_code = STORM` - one is LOW, the other
is HIGH. A `VEHICLE` strike that knocks out one transformer is LOW; a `VEHICLE` strike
that takes down a substation feeding thousands of customers is HIGH.

Weigh the instance's own evidence:

- **Impact count** - customers/outages affected. `min_impact_count_for_major` above is
  the enforced floor for HIGH - at or above it, HIGH is mandatory regardless of type.
- **Outage count** - how many separate outages this event has generated so far.
- **Duration** - how long restoration is taking or is expected to take.
- **Region** - whether the affected area spans multiple feeders/substations or just one.

Recommend LOW or MEDIUM freely below the enforced floor. The deterministic caller only
accepts a HIGH recommendation once `impact_count` crosses `min_impact_count_for_major` -
same "model proposes, code validates" split as the outage status-transition guard.
