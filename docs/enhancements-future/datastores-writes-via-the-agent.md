# Route Outage Writes Through the Agent (Authorized ORM Path)

## What it is

Today the chat/ReAct path and the REST write path are fully separate code
paths that happen to share a class name. `OutageAgent.handle()` (invoked by
the ReAct loop) only ever calls `self._mcp.query()` - read-only NL2SQL
through pgEdge. `OutageAgent.create_outage()/.transition()/.list_outages()/
.list_crews()` (invoked only by `ApiRoutes`) call `OutageLifecycleService`
directly via the ORM - the app's one sanctioned write path. The two never
call each other. This doc captures an idea to let an authorized chat
request write too, through the same agent, instead of only through a
separate REST call.

## What it does

Lets an operator ask for a state change in natural language (e.g. "assign
the North crew to the transformer outage on Feeder-12") and have the
Outage Agent - once request/user authorization is confirmed - perform the
write itself via `OutageLifecycleService`, instead of requiring a second,
separate REST call (`POST /outages/{id}/transition`) from the UI.

## How it'd work

The wiring for this already half-exists and doesn't need to be built from
scratch:

- `DomainAgentFactory.get("outage")` already injects
  `outage_lifecycle_service` into the exact same `OutageAgent` instance the
  ReAct loop dispatches to. `handle()` simply never uses it today.
- So the plumbing question is not "how do we get the service to the
  agent" - it's already there - it's "what has to exist before `handle()`
  is allowed to call it."

Two things are missing, both by design (Phase 0 explicitly excludes them,
per `AGENTS.md`):

1. **No write-capable intent exists.** `Intent` has no `CREATE_OUTAGE`/
   `TRANSITION_OUTAGE` value, and `RoutingMap` never authorizes a write
   action - every intent today only ever authorizes read dispatch. The
   classifier has no way to even express "the user wants to change
   something," so nothing upstream could route to a write today.
2. **No authorization model exists.** There is no user/role/permission
   concept anywhere in the code right now to gate a write on.

## How we'd implement it (sketch, not a commitment)

1. Add a new intent (e.g. `OUTAGE_WRITE`) with its own `RoutingMap` entry,
   so the classifier can express "this is a change request," distinct
   from every existing read intent.
2. Add an authorization check (whatever this app's eventual auth model
   turns out to be) that the request must pass before `handle()` is even
   allowed to consider a write branch.
3. In `OutageAgent.handle()`, branch: if the (validated, code-checked)
   intent is the write intent and required fields are present
   (`outage_id`/`to_status`/`crew_id` etc.), call
   `self._outage_lifecycle_service.transition(...)` directly - the same
   ORM call the REST path already uses - instead of `self._mcp.query()`.
4. Keep the decision to write itself deterministic, not something the
   ReAct loop free-reasons into. The model can extract/propose the
   fields; code must independently validate them (same "model proposes,
   code validates" split already used for `outage_note_triage`) before
   `OutageLifecycleService` is ever called.

## Business Value

A single, more natural interaction for operators ("just tell it what
happened") instead of a UI form-driven REST call, while keeping the
existing guarantee that writes are still deterministic and validated code,
never a raw model action - reinforcing this app's core teaching thesis
rather than working around it.

## Risks/Constraints

- This blurs a boundary that is currently very clean: read-only chat vs.
  write-only REST. Any implementation must keep the _decision to write_
  fully deterministic (code-checked fields, not model free-reasoning),
  or it re-introduces exactly the kind of non-determinism this app exists
  to guard against.
- Depends on two pieces of scope explicitly deferred out of Phase 0 (auth,
  write-capable intents) - this is a Phase 2+ idea, not a small addition.
- Needs careful thought on user-facing failure modes: a rejected/ambiguous
  write request from chat must fail loudly and safely, not silently do
  nothing or write the wrong thing.

## Discussion notes

Raised while reviewing the architecture diagram (2026-09-20), after
confirming via direct code read that `OutageAgent.handle()` does not and
currently cannot write - the ReAct-invoked instance already has
`outage_lifecycle_service` injected, it's just unused today. Revisit when
there's time to design this properly; there's likely an elegant version of
this where "everything goes through the agent," but it needs the intent
and authorization pieces built first, not just a code branch in `handle()`.
