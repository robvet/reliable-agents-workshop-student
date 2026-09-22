---
hazard_keywords:
  - fire
  - fires
  - spark
  - sparks
  - sparking
  - arc
  - arcing
  - explosion
  - explode
  - exploding
  - gas
  - smoke
---

# Outage Note Triage

Judge whether a field crew's free-text note describes something more dangerous or
severe than a routine outage - never invent facts beyond what the note actually says.
Most notes describe a routine repair; only escalate when the note itself names a
safety hazard.

Recommend `escalate: true` and `severity: HIGH` when the note describes an active
safety hazard - fire, sparking, arcing, an explosion, a gas smell, or smoke. These are
never routine, regardless of how calmly they're phrased.

Recommend `escalate: true` and `severity: MEDIUM` when the note describes worse
conditions than a routine single-asset outage without naming an active hazard - e.g.
multiple assets affected, a downed line blocking a road, or a much larger customer
count than typical - but nothing on fire, arcing, or leaking gas.

Otherwise recommend `escalate: false`. A routine repair note ("replaced the blown
fuse," "crew en route," "waiting on parts") should never be escalated just because it
mentions equipment by name.

`hazard_keywords` above is the enforced floor for a HIGH recommendation - the
deterministic caller only accepts an `escalate: true` / `severity: HIGH` outcome when
at least one of these words actually appears in the note text. Same "model proposes,
code validates" split as the outage status-transition guard and the event severity
classification skill.
