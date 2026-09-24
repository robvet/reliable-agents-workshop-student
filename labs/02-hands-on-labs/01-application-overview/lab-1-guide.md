# Lab 1: Application and Architecture Tour

## Introduction

This instructor-led lab is a hands-on tour of the application and its code. The instructor will guide the class through each activity while students run the same steps on their own computers.

Together, you will explore the user experience, operational use case, architecture, data, tests, and key application scenarios. You will also examine the critical code paths that combine model-driven reasoning with deterministic engineering controls to improve agent and agentic-system reliability.

## Lab format

This lab is completed as a team:

1. The instructor introduces each area of the application.
2. The instructor demonstrates an activity or code path.
3. Students mirror the activity in their local environment.
4. The class discusses what happened and where reliability controls are applied.

No code changes are required in this lab.

### Predict before you look

One instruction applies to every activity below: **say what you expect before you run it.**

This is not a study habit. It is the test. A system built on deterministic controls should be predictable, so if you can read the routing rules and correctly call which agents a request is permitted to use, the design is doing its job. When a prediction is wrong, you have found either a gap in your understanding or a place where the system is less constrained than it appears. Both are worth the minute it takes to guess out loud.

## Learning objectives

By the end of this lab, you will be able to:

- Explain the application's operational use case and user experience.
- Describe the major architecture components and their responsibilities.
- Follow a request through classification, reasoning, dispatch, data access, and response assembly.
- Identify the application's core data and how agents access it.
- Run the tests and explain what key behaviors they verify.
- Recognize where deterministic engineering controls constrain and validate model behavior.

## Before you begin

Start the application from the repository root:

```bash
./start
```

This launches three processes. Wait for all of them to report ready:

| Process     | Port    | Purpose                                  |
| ----------- | ------- | ---------------------------------------- |
| MCP server  | `:8000` | Natural-language-to-SQL data service     |
| Backend API | `:8010` | FastAPI application and orchestration    |
| Frontend    | browser | Chat interface and Execution Trace panel |

If a process reports a traceback instead, scroll up in the terminal before continuing.

## Guided tour

### 1. Explore the application

Review each area of the user interface and identify how a user submits a request, follows its execution, and receives the final response.

Find the **Execution Trace** panel. You will use it in every activity that follows. It is not a debug view bolted on afterward - each entry is a `TraceStep` that a component deliberately emitted, which is why the trace can show you a decision the application then refused to act on.

### 2. Understand the use case

Discuss the asset-event response scenario, the operational questions the application answers, and the roles of the specialized domain agents.

Seven agents exist: `asset`, `event`, `outage`, `crew`, `reliability`, `weather`, and `direct_query`. As a class, predict which ones a question about restoring power to a neighborhood would need before looking at how the application routes it.

### 3. Review the architecture

Walk through the end-to-end request path from the user prompt to the rendered answer. Identify the model calls, typed boundaries, deterministic control points, domain agents, and data-access path.

Count the model calls on a single request. Then count the deterministic checks between them.

### 4. Explore the data

Review the application's core data and relationships. Follow one agent request through the MCP and natural-language-to-SQL read path.

Note the two tools the MCP server exposes - `ask(question)`, where a model generates the SQL, and `run_sql(query)`, where the caller supplies it. Both pass the same validation, and both run against a connection that holds a read-only grant.

### 5. Run the tests

Run each focused suite and review the behaviors it protects:

```bash
./test-lab2     # 4 tests - intent classification
./test-lab3     # 3 tests - orchestration and the allow-list
./test-lab4     # 6 tests - the domain agent read path
```

Every one of these runs offline. There is no model call, no MCP server, and no database - the boundaries are mocked. That is possible only because each component depends on an interface rather than a concrete client, and it is why these tests give the same answer every time.

Connect each test to the application component and reliability principle it verifies.

### 6. Run key scenarios

Before submitting each prompt, predict the intent and the agents that intent permits. Then submit it and compare your prediction against the Execution Trace.

| Prompt                                                      | Your predicted intent | Your predicted agents |
| ----------------------------------------------------------- | --------------------- | --------------------- |
| `Report an outage at Central substation`                    |                       |                       |
| `What is affected by the outage at FDR-204?`                |                       |                       |
| `How many transformers were inspected in the last 30 days?` |                       |                       |
| `Write a poem about the ocean`                              |                       |                       |

The last prompt is the most instructive. Watch what the Execution Trace shows - and what it does not.

> **Deterministic engineering: the allow-list is a lookup, not a request.**
> `UNKNOWN` permits zero agents, so the last prompt dispatches nothing. That outcome does not depend on the model agreeing to decline it, and no phrasing of the request can widen the list. Compare it with the first prompt, where `EVENT_RESPONSE` permits five agents and the reasoning model may choose among those five and no others.

### 7. Walk through critical code

As a class, inspect the code that implements:

| Boundary                        | Where it lives                                           |
| ------------------------------- | -------------------------------------------------------- |
| Typed intent classification     | `src/app/intent/llm_intent_classifier.py`                |
| The intent allow-list           | `src/app/policy/routing_map.py`                          |
| Orchestration and stopping      | `src/app/agents/orchestrator.py`                         |
| Typed requests and results      | `src/app/models/agent_request.py`, `agent_result.py`     |
| MCP-backed data access          | `src/app/agents/asset_agent.py`, `tools/i_mcp_client.py` |
| Deterministic response assembly | `src/app/services/response_assembler_service.py`         |

For each code path, identify what the model proposes, what deterministic code validates or controls, and how that boundary improves reliability.

Labs 2, 3, and 4 will have you implement three of these yourself.

## Check your understanding

Before moving on, make sure you can answer these without looking:

- Where does the user's unstructured text stop driving decisions?
- Which component decides that an agent is allowed to run, and which component runs it?
- Name three conditions that can end the orchestration loop. Which one does the model control?
- What is the difference between a request the system classified as `UNKNOWN` and a request that produced an `ERROR`?
- Why can the focused tests run without a model, a database, or the MCP server?

## Code changes

None. This is an instructor-led application and architecture tour.
