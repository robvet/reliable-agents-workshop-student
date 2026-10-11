# Intent Classification Notes

- Lab 2: Customer gets a shell of the llm_intent_classifier class and builds out the workflow and implementation detail for the intent classification.

- Lab 2 (Intent Classifier) — solid size, good pick.
  Self-contained, single model call, already has "Architectural Insights" teaching comments baked in (Adapter pattern, response_format, the ERROR vs UNKNOWN distinction the docstring literally calls out as "the exact bug this class used to have"). That's a ready-made checkpoint: have the lab force a fault and assert the customer's implementation returns ERROR, not UNKNOWN. Low risk, high teaching value.
