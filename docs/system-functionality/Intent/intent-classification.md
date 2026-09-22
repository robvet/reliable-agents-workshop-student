# Intent Classification

## What it does

Intent classification is the single hop in the pipeline where a user's raw,
unstructured text gets turned into a validated, typed decision: exactly one
of 7 predefined intents, plus any entities (asset id, feeder, event id, etc.)
the model could extract. `LlmIntentClassifier.classify()` is the only place
this happens - it takes a `user_prompt` (and optional conversation `history`)
and returns an `IntentResult`, never a raw string.

The 7 intents (`src/app/models/intent.py`): `EVENT_RESPONSE`,
`SITUATIONAL_AWARENESS`, `RELIABILITY`, `MAJOR_EVENT`, `CROSS_DOMAIN`,
`DOMAIN_LOOKUP`, `UNKNOWN`. An 8th enum value, `ERROR`, exists but is a
system-only fault state - the model is explicitly forbidden from choosing it.

## Why it's critical for reliability

Intent classification is the highest-leverage point in this kind of system,
because everything downstream - `RoutingMap`'s allow-lists, which domain
agent gets dispatched, the entire security boundary around what an agent is
even permitted to reach - is built on trusting that one classification. A
vague or drifting taxonomy poisons every guarantee built on top of it. The
whole "model proposes, code validates" thesis this app is built around only
holds up if what the model is proposing is itself well-defined.

**This is also the one deliberately-scoped moment of real non-determinism.**
The class itself (`LlmIntentClassifier`) has zero decision logic in Python -
no scattered `if message contains X` branching. It's a thin adapter: build
prompt -> call model -> validate/wrap failures. All the actual judgment -
which of the 7 intents applies - lives in one prompt file
(`intent_classifier_task.jinja2`), not in code. That's a code-quality claim,
not a determinism claim: the classification itself is, and always will be,
non-deterministic. The same message could, in principle, produce a different
intent on a different call - reasoning models here don't even accept
`temperature=0` to pin that down. That's inherent to using an LLM for this
at all, not a flaw.

This is by design, not a gap. Look at the architecture diagram's own legend:
the Intent Classifier box is colored amber ("LLM call - non-deterministic"),
explicitly distinct from the blue "deterministic code" boxes around it. The
system's actual determinism guarantee is never "the model picks the same
intent every time." It's: **whatever** the model picks, code immediately
bounds it - to one of 7 legal enum values (schema enforcement, not prose) and
to a fixed, pre-approved agent allow-list (`RoutingMap`) before anything
downstream ever runs. Determinism is applied _around_ the model's judgment,
not _to_ it. Reliable Agents' engineering discipline isn't "eliminate model
unpredictability" - it's "confine it to one well-defined hop, then validate
and constrain everything that follows."

## How it works

**Step 0 - Initialization (once, at startup, not per request)**
`LlmIntentClassifier.__init__()` builds one Agent Framework `Agent` and keeps
it for the life of the app:

- `OpenAIChatClient` bound to `settings.intent_slm_deployment` - a specific,
  smaller/cheaper model deployment, since this is a quick classification,
  not deep reasoning.
- `instructions` = the one-sentence system persona rendered from
  `system/intent_classifier_persona.jinja2`.
- `default_options = {"reasoning": {"effort": "high", "summary": "detailed"},
"store": False}` - reasoning params live on the agent, not re-sent per
  call; `store: False` keeps the service from persisting the call server-side.

**Step 1 - A request arrives**
`Orchestrator.process_request_stream()` calls
`self._intent_classifier.classify(request.user_prompt, request.history)`.

**Step 2 - Build the per-call prompt**
`classify()` renders `intent_classifier_task.jinja2` with `user_prompt` and
`history`. This file - not the system persona file - is where the real task
lives: the 7 intent definitions, 7 ordered decision rules, tie-breakers,
worked examples, the ERROR-is-forbidden warning, the
`needs_downstream_assets` rule, and (when `history` is non-empty) the
continuation-vs-new-topic instructions.

**Step 3 - Call the model with a schema lock**

```python
response = await self._agent.run(prompt, options=ChatOptions(response_format=IntentResult))
```

`response_format=IntentResult` is the real enforcement layer. Pydantic turns
`IntentResult`'s fields into a JSON schema - `intent` becomes an `enum` of
exactly the 7 legal string values (`ERROR` is on the enum too, but the prompt
forbids the model from choosing it). The model is structurally incapable of
returning anything that doesn't validate against that schema.

**Step 4 - Two failure branches (code-decided, never model-decided)**

- The call throws (network/auth/service fault) -> code builds
  `IntentResult(intent=Intent.ERROR, error=...)` itself.
- The call succeeds but `response.value` isn't a valid `IntentResult` ->
  same result, different message.

Both are logged and span-tagged, then returned immediately - the model's
opinion is never consulted to produce `ERROR`. This distinction matters:
`UNKNOWN` means "the user asked something this app can't help with";
`ERROR` means "our system faulted." Collapsing a fault into `UNKNOWN` would
let an outage masquerade as a benign fallback.

**Step 5 - Success path**
`result = response.value` is already a validated `IntentResult`: `intent`,
`entities` (asset_id, feeder, substation, location, event_id,
needs_downstream_assets), `confidence`, `reasoning`, `continues_previous`.
Code doesn't touch `intent` here - it logs/traces it and returns it as-is.

**Step 6 - Back in the Orchestrator**
`intent_result.intent` is looked up in `RoutingMap.allowed_agents(intent)` to
get a fixed, hardcoded agent allow-list for that intent. This is the exact
point where "the model proposed, code now constrains" becomes real: no
agent outside that list can ever be dispatched for this request, no matter
what a later reasoning step proposes.
