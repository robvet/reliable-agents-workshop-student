# Interactive Application Overview Lab Notes

- Lab 1: An interactive overview of the app. The customer reviews the app section, but has some kind of interactive exercise that requires them to explore and understand the app to answer.
- Good progression — mirrors the actual pipeline (classify → orchestrate → agent), and Lab 1 as scaffolding before code is the right call. Here's what I'd flag after reading the actual classes:

- Lab 1 — make the "interactive exercise" concrete now, not later.
  Given the architecture SVG already exists, good exercise shapes: a "trace a request" walkthrough where they have to name which box handles a given failure (UNKNOWN vs ERROR vs agent exception vs loop-exceeds-8), or a file scavenger hunt ("find the allow-list," "find where HTTP 200 already went out before any pipeline code ran"). Ties the business-case narrative to real files instead of being purely conceptual.

Sequencing — agree, do Lab 1 last. It depends on the other three being finished: you can't send someone on an "explore the app + quiz them" tour of the intent classifier, orchestrator, and outage agent until you know exactly which lines/behaviors in those files are the ones worth quizzing on. Building 2/3/4 first means Lab 1's quiz questions write themselves from real content instead of you guessing what's interesting.

Lab 1 shape — architecture diagram open + code exploration + quiz — good format, with one addition:

Quiz questions should target the specific reliability details the customer will later implement in Labs 2–4, not just "what does this file do." E.g., if Lab 2's blank is the ERROR vs UNKNOWN branch, Lab 1 should have already asked "what's the difference between these two, and why does it matter?" — so by the time they hit the blank in Lab 2, they're implementing something they already reasoned about, not seeing it cold.
That makes Lab 1 double as a primer/answer-key preview for the other three, which also means I can't really finalize Lab 1's questions until we know each lab's specific blanks (reinforces doing it last).
Format-wise: a running numbered list of "open file X, answer Y" checkpoints against the SVG + real files (orchestrator.py, llm_intent_classifier.py, outage_agent.py, routing_map.py) reads well as a companion doc while the app is actually running — should confirm you want them running the live app side-by-side (asking it a question, watching the Execution Trace panel) rather than just reading code statically. That's a much stronger "explore and understand" hook if the app supports it.
