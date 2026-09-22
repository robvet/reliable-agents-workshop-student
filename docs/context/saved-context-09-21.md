# Saved Context - 2026-09-21

Supplementary notes carried over from a prior conversation, on Agent Framework
mechanics and system/user-role prompt design. Written to support the "Study
the system prompt" item in the Intent Classification Lab.

## OpenAIChatClient / Agent / AgentResponse - what each one actually is

Verified directly against the installed SDK source
(`.venv/lib/python3.11/site-packages/agent_framework/`), not from memory:

- **`OpenAIChatClient`** (`agent_framework.openai`) is a client wrapper - a
  reusable connection config (endpoint, model deployment, credential). It
  targets Azure OpenAI's **Responses API**, not Chat Completions - confirmed
  from the module's own docstring: `"OpenAIChatClient (Responses API)"`. It
  is a "fully-featured client with all layers applied" over a lower-level
  `RawOpenAIChatClient`. The client itself does not return anything to the
  caller - it is handed to an `Agent` as a dependency.
- **`Agent`** (`agent_framework.Agent`) is what you actually call `.run()`
  on. It pairs a client with `instructions` (the system prompt) and
  `default_options` (e.g. `reasoning`, `store`). This is the SDK-level
  "agent" concept - a generic wrapper for making one kind of model call. It
  is unrelated to this app's own "domain agent" concept (`AssetAgent`,
  `CrewAgent`, etc.) - same English word, two different things.
- **`AgentResponse`** is what `Agent.run()` returns (confirmed from
  `_agents.py`'s own docstring example, which imports
  `AgentResponse` alongside `BaseAgent`/`AgentSession`). Code reads
  `response.value` (the structured result, when `response_format=` is used)
  and `response.messages` (to pull reasoning-summary text, etc.).

Chain: `OpenAIChatClient` = how to reach the model -> `Agent` = the thing you
call `.run()` on -> `AgentResponse` = what comes back.

This app builds **four separate, private `Agent` instances**, each bound to
one narrow task - none of them are "domain agents" and none appear as boxes
in the DOMAIN AGENTS row of the architecture diagram:

| Class | Agent name | Model deployment |
|---|---|---|
| `LlmIntentClassifier` | `"intent-classifier"` | `settings.intent_slm_deployment` |
| `ReActReasoning` | (same pattern) | `settings.intent_slm_deployment` |
| `LlmOutageNoteClassifier` | `"outage-note-triage"` | `settings.intent_slm_deployment` |
| `AnswerNarratorService` | `"answer-narrator"` | `settings.inference_lm_deployment` (falls back to intent SLM if unset) |

## Why system-role vs. user-role placement matters

In most aligned model behavior, system-role content carries more instruction
authority than user-role content: system is meant to be the stable,
authoritative rule set the model follows; user is the data/question being
acted on. Putting static rules in the user-role prompt (as this app
originally did for intent classification) is backwards from that
convention, for two concrete reasons:

1. **Weaker instruction separation.** If the rules and the user's raw,
   potentially-adversarial text sit in the same message role, there is less
   structural separation between "instructions" and "content that could try
   to argue with them" (a real prompt-injection consideration, not just
   style).
2. **No functional reason to re-send static content per call.** Rules that
   never vary by request (a fixed taxonomy, decision order, examples) are
   boilerplate being reprocessed on every call for no benefit if they live
   in the per-request template.

One plausible additional benefit, **flagged as unverified**: some model
APIs cache a stable system-prompt prefix server-side for latency/cost. If
Azure OpenAI's Responses API does this here, splitting static rules into
the system persona could reduce repeated processing - not confirmed for
this specific setup.

## Applied fix: the intent-classifier prompt split (2026-09-21)

- `src/app/prompts/system/intent_classifier_persona.jinja2` - rendered
  **once**, at `Agent` construction. Now holds everything static: the 7
  intent definitions, the 7 decision rules, tie-breakers, all examples, the
  `ERROR`-forbidden warning, and the entity-extraction instructions
  (including `needs_downstream_assets`).
- `src/app/prompts/intent_classifier_task.jinja2` - rendered **per call**.
  Now holds only what actually varies per request: the
  `{% if history %}` continuation-vs-new-topic block and
  `{{ user_prompt }}`.
- No Python code changes were required - `LlmIntentClassifier` already
  called both files with the same variable names; only the content moved
  between them. Verified by rendering both templates directly (with and
  without `history`) after the split.
