# Lab Planning Overview Notes

Makes sense, and it directly fixes my Lab 3 sizing concern: if the workflow/plumbing is already there and commented, the "build" work in every lab is scoped to the same kind of thing — the reliability-pattern lines, not the scaffolding — so all four labs land at a similar size and teach the same lesson (spot and implement the guardrail) instead of "write a class from memory."

A few things worth nailing down now, since they apply across all four labs, before we draft any one of them:

1.  Blank format/mechanic — how do we mark what's missing? Options: # TODO(reliability): ... comments with a one-line hint, a paired "solution" file for the instructor, or a diff-style answer key. Whichever we pick should be consistent across all 4 labs so the student experience doesn't shift lab to lab.

2.  Verification signal — you said "touch each file for the reliability detail, not the workflow." The strongest way to prove they got it right isn't eyeballing output, it's a test going green. I noted earlier tests has no test_llm_intent_classifier.py and no test_outage_agent.py, and test_orchestrator_errors.py only covers error paths. If we want tests as the lab's pass/fail signal, we should write those alongside the lab content (kills two birds).

3.  What counts as "the reliability detail" per class — worth agreeing per-lab before writing, e.g.:
    a. Intent Classifier: the ERROR vs UNKNOWN branch (fault → ERROR+detail, never UNKNOWN)
    b. Orchestrator: allow-list check before dispatch, MAX_STEPS cap, the no-progress dedup guard
    c. Outage Agent: the try/except around the MCP call that fails the step rather than swallowing it, the hazard-keyword double-check that overrides the model's own escalation opinion

That last point is really the per-lab planning work — so let's do exactly what you asked: one at a time. Lab 1 is the odd one out since it's not a code-blank exercise (no class file, it's exploratory), so worth confirming: is Lab 1 staying as a pure "explore the running app + docs" exercise, separate from the blank-the-guardrail mechanic in Labs 2–4? If yes, want to start planning Lab 1's actual exercise content now, since that's your active file?
