# Reliable Agents - Agent Instructions

Single source of truth for this repo's project directives. These apply to every session
and override default scaffolding behavior. Read by both Copilot CLI and VS Code agent mode.
(Chat-style prefs live in the global user instructions file; `.github/copilot-instructions.md`
just points here to avoid conflicting instruction sets.)

## Project

Reliable Agents: a reliable multi-agent system for asset-event response. A deterministic
orchestrator identifies intent, routes, and composes; specialist agents (Asset, Event,
Crew, Reliability) do the work. The model proposes; deterministic code validates,
authorizes, and reflects on every action.

**Current phase: Phase 0 - typed skeleton with stubbed agents.** Prove the pipeline
(intent -> route -> dispatch -> compose) with agents returning canned data. No tools,
no DB, no durability.

## Golden rules (non-negotiable)

1. **Reuse existing code. Do not recreate what exists.** The plumbing already exists and
   must be used as-is: `main.py`, the FastAPI app and `api/`, `config/`, `observability/`
   (logging + telemetry), `utils/`, `prompt_repository.py`, `models/`, and `agents/`
   (orchestrator, provider agents, `i_agent.py`). Check for existing functionality before
   creating any file.
2. **If you must modify existing shared code, STOP.** Do not modify `main.py`, `api/`,
   `config/`, `observability/`, or `utils/` without approval. Halt and surface the
   proposed change for review first. Never silently edit shared plumbing.
3. **Create only what is absolutely needed.** No speculative files, folders, abstractions,
   or dependencies. If it isn't referenced by the typed pipeline or the four stubbed
   agents, it must not exist. No "for later" scaffolding.

## Code style (hard rules)

- **No code outside a class.** No module-level functions, no loose script code, no
  top-level logic. Everything lives in a class method.
- **One class per file.** Each file defines exactly one class, and the file is named after
  the class.
- **Only permitted module-level members:** the `Intent` enum and `ROUTING_MAP`, and only
  where a class wrapper would be artificial.
- Type everything. Use Pydantic models for all message contracts.
- **Structured, maintainable, testable.** Follow SOLID. Think C#/Java structure first.

## Architecture rule (the typed pipeline)

- From that point on, **every hop is a validated Pydantic object.** No free text between
  the intent and the final rendered answer.
- **No agent ever returns a string.** Agents return a populated `AgentResult`. The
  human-readable answer is _rendered_ from `ChatResult` at the end, by code.
- Control flow is deterministic. The model proposes (intent, later tools); deterministic
  code validates and authorizes before anything executes.

## Phase 0 non-goals (do not add)

No SQL / DB access. No real tools. No durability or state persistence. No retries. No auth
enforcement. No multi-model debate/aggregate flow.

## How to work - rules of the road

**Scope.** These rules govern state-changing actions: writing, creating, deleting, running,
configuring. For a factual question or read-only analysis, just answer - no plan, no approval.

**Two speeds - act vs. propose.** The test: does the change alter the SHAPE of the system,
or just its CONTENTS?

- CONTENTS -> propose first, then wait for "yes"/"do it"/"Y", same as SHAPE: clear-cause
  bug fixes, typos/comments/docstrings, behavior-preserving local refactors, adding a test,
  tightening a type, wiring something already specified - anything reversible in one
  `git checkout`.
- SHAPE -> propose first, then wait for "yes"/"do it"/"Y": new files/folders/classes/
  dependencies, changes to shared plumbing (`main.py`, `api/`, `config/`, `observability/`,
  `utils/`), new abstractions or patterns, contract changes (Pydantic models, interfaces,
  routing), anything spanning multiple modules or hard to undo.
- Unsure which bucket? Doesn't matter - propose first either way and wait for approval.

**Explain what you changed.** For ACT changes, show exact files and a tight before/after -
no surprises. For PROPOSE changes, state the problem, the fix, and the consequences before acting.

**Keep it simple - this is the point.** Start with the simplest solution; discuss enhancements
only after it works. The primary risk is premature complexity and scope drift. Guard against it
above all else.

**Ask when genuinely unsure.** If the request is ambiguous in a way that changes the outcome,
stop and ask. Don't guess. Don't ask reflexively.

**Warn about consequences.** If a change breaks something, adds complexity, or introduces
dependencies, stop and explain first. No hidden files added anywhere.

**One slice at a time.** Build and validate in the order given by the Phase 0 spec; do not
scaffold the whole phase at once.

**Be brief.** Commit when confident. No preambles.

## Exception: `src/mcp_sql/`

Everything above applies to Reliable Agents only. `src/mcp_sql/` is a separate,
disposable sandbox POC and is exempt from all of it.

- **Code style rules above do NOT apply.** `src/mcp_sql/` is flat modules with
  module-level functions. No classes, no one-class-per-file, no Pydantic
  message contracts. Do not refactor it to match Reliable Agents.
- **Spec is `specs/spec-mpc-postgres.md`.** It is the contract. Everything under its
  "Out" list is forbidden. Do not add scope.
- **Disposable sandbox.** No customer, no security review, no production
  path. Auth models, secret management, hardening, Entra ID, Key Vault,
  managed identity are out of scope by definition. Do not add them.
- **Blast radius:** never touch `src/app/**`, `frontend/**`, root
  `pyproject.toml`, `requirements.txt`, the root `.venv`, or CI. Read them for
  conventions only.
- Never run `pip install -e .` against the root venv — always run from inside
  `src/mcp_sql/` with `src/mcp_sql/.venv` active.
- One task at a time. Stop and report after each.
