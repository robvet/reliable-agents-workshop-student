# Lab 2: Intent Classification

Implement structured intent classification and explicit model-failure handling.

## Learning objectives

- Convert unstructured user input into a validated `IntentResult`.
- Request schema-constrained model output.
- Preserve the distinction between an unclassifiable request and a system fault.
- Verify behavior with focused tests and the live Execution Trace.

## Build target

Implement the classification workflow in `LlmIntentClassifier.classify()` while retaining the provided client construction and telemetry helper.

## Lab activities

1. Review the fixed intent taxonomy and `IntentResult` contract.
2. Render the per-request classification prompt.
3. Call the model with `response_format=IntentResult`.
4. Validate the returned structured value.
5. Return `Intent.ERROR` with detail for call or response failures.
6. Run the focused classifier tests.
7. Observe successful and failed classifications in the application.

## Success criteria

- Valid prompts produce typed classification results.
- Valid out-of-scope prompts produce `UNKNOWN`.
- Technical failures produce `ERROR` with diagnostic detail.
