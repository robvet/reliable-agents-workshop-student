# Lab 4: Build a Domain Agent

> **Lab status:** Detailed implementation instructions are in development. This page outlines the planned lab experience.

## Introduction

In this lab, you will complete the read path for a domain agent. The agent receives a typed request, turns the request into a domain-language question, accesses data through the injected MCP client, and returns a typed result to the orchestrator.

The goal is to keep the agent focused on domain behavior. It should ask for the information it needs without embedding database table or column knowledge.

## Learning objectives

By the end of this lab, you will be able to:

- Receive and use a typed `AgentRequest`.
- Build a domain-language question from the user request and extracted entities.
- Access data through the injected MCP client.
- Normalize returned data into an `AgentResult`.
- Add a concise trace step.
- Surface MCP failures to the orchestrator.

## Architecture context

The orchestrator dispatches a typed request to the selected domain agent. The domain agent uses the MCP client to retrieve data, normalizes the returned payload, and sends a typed result back to the orchestrator.

_Architecture walkthrough and code references will be added during the full Lab 4 authoring pass._

## Lab exercise

You will complete the selected domain agent's read path, from prompt construction through typed result creation.

### Planned steps

1. Review `AgentRequest`, `AgentResult`, and the domain-agent interface.
2. Build the domain-language MCP question.
3. Invoke the injected MCP client.
4. Normalize the returned rows into the agent's typed data shape.
5. Construct the `AgentResult` and add a concise trace step.
6. Propagate MCP failures instead of returning false success.

_Detailed code instructions and checkpoints are coming next._

## Test activities

- Run the focused domain-agent tests.
- Execute an end-to-end request through the completed pipeline.
- Confirm that successful tool output becomes a valid `AgentResult`.
- Confirm that tool failures stop the orchestration path correctly.

_Exact commands and expected results will be added with the completed exercise._

## Success criteria

You will have completed the lab when:

- The domain agent remains independent of database tables and columns.
- Successful MCP output is normalized into a valid `AgentResult`.
- The result includes a concise trace step.
- MCP failures are surfaced to the orchestrator.
