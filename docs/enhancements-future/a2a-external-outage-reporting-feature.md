# A2A - External Outage Reporting Feature

**Assumption, labelled as an assumption:** "A2A" is read here as the emerging
Agent2Agent protocol (cross-vendor agent interoperability - one AI agent
calling into another system's agent, not this app's own internal
orchestrator-to-domain-agent calls). If a different meaning was intended,
this whole doc needs revisiting.

# What it is

A new _inbound_ integration surface: an external agent (a partner utility's
own monitoring agent, a SCADA/AMI head-end agent, anything outside this
app) reports a candidate outage into Reliable Agents over the A2A protocol,
instead of a human typing it into the Outage Management UI. This is the
opposite direction from everything else in this app today - Reliable
Agents' own agents call out to MCP/NL2SQL; this is Reliable Agents
_receiving_ a report from someone else's agent.

## What it does

An external system publishes a report shaped like "outage at/near X,
described as Y, source system Z" against Reliable Agents' A2A-facing
endpoint. Reliable Agents resolves that report to a real asset and
deterministically creates the outage - through the exact same write path
the UI already uses, not a parallel one.

## How it'd work

1. Publish an A2A "Agent Card" describing this app's outage-reporting
   capability at a well-known endpoint, per the A2A spec.
2. Add a new inbound task/message endpoint that accepts a structured
   external report (asset identifier or location, free-text description,
   severity signal, source system name).
3. Deterministic code (not a model) resolves the reported asset against
   `grid_assets` - by name if given, or by lat/long proximity if the
   external system only has coordinates. Reject, don't guess, if nothing
   resolves confidently.
4. Call `OutageLifecycleService.create_outage()` - the same entry point
   the internal UI already uses. No second, parallel write path.
5. Optional: an LLM step could triage a free-text external description into
   structured severity/impact fields, mirroring the existing
   `outage_note_triage` skill pattern (model proposes a read; code
   independently validates before writing anything).

## How we'd implement it

A new small adapter in front of `OutageAgent`/`OutageLifecycleService.create_outage()`
(e.g. `A2AInboundAdapter`) that translates an A2A-shaped payload into the
same `asset_id`/`event_id`/`impact_count` arguments the internal flow
already takes. Needs, at minimum:

- **Asset resolution** - external systems won't know our internal UUIDs;
  resolving by name or geo-proximity is the hard part of this feature, not
  the protocol plumbing.
- **Idempotency** - an external system may retry the same report; a
  de-dupe key is needed so a retry doesn't create a duplicate outage.
- **Auth/trust boundary** - who is allowed to call this endpoint at all.
  Not solved here, just named - see Risks/Constraints.

## Business Value

Shows this app's core teaching thesis (deterministic control wrapped around
agentic behavior) applied to a real, currently relevant industry pattern:
cross-vendor agent interoperability. It's also operationally realistic -
many real outages are first detected by another system (SCADA, AMI,
a partner's own monitoring agent), not typed by a person. A compelling,
differentiated workshop story: "here's how an external agent reports into
our system without bypassing our deterministic guardrails."

## Risks/Constraints

- Security/auth for any external-facing write path is a real concern, not
  a demo afterthought - must be solved properly before this goes anywhere
  beyond the workshop.
- Asset resolution (their identifier -> our `asset_id`) is genuinely hard;
  an ambiguous or unmatched report needs a clear rejection/escalation path,
  never a silent best-guess match.
- A2A is an emerging protocol; the ecosystem (client/server libraries) is
  still moving, so implementation details here may drift before this is
  actually built.
- Must not skip the existing deterministic guardrails just because the
  caller is "another agent" - same validation the human UI path already
  gets, no exceptions for a trusted-looking source.

## Discussion (notes)

Idea captured 2026-09-20, right after finishing the Data Dictionary
rewrite. Not scoped or estimated yet. Ties directly into the app's "model
proposes, code validates" thesis: even a report arriving from another AI
agent is treated as a proposal that deterministic code validates before a
real outage record is created - never trusted blindly just because the
source is also an agent.
