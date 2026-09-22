# Lab 3: Reliable Orchestration

Implement the deterministic control loop that bounds and validates model-proposed actions.

## Learning objectives

- Separate model proposals from application-controlled execution.
- Bound the ReAct loop with a fixed step limit.
- Enforce intent-specific agent authorization.
- Stop execution when no new data is produced.
- Emit visible progress throughout the request.

## Build target

Complete the ReAct control-loop portion of `Orchestrator.process_request_stream()`. Memory, telemetry, response assembly, and stream infrastructure remain provided.

## Lab activities

1. Obtain the allowed agents for the classified intent.
2. Build the catalog presented to reasoning.
3. Request and trace the next model-proposed decision.
4. Reject an agent outside the allow-list.
5. Dispatch an available agent with a typed `AgentRequest`.
6. Collect and emit its typed `AgentResult`.
7. Stop on completion, duplicate meaningful data, or `MAX_STEPS`.
8. Run the focused orchestration tests.
9. Observe a multi-agent request in the Execution Trace.

## Success criteria

- Unauthorized agents never execute.
- The loop terminates under every defined stopping condition.
- Each completed step appears in the live trace.
- The request ends with one final or error event.
