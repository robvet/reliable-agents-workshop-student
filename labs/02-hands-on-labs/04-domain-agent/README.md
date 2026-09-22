# Lab 4: Domain Agent

Implement the reusable pattern by which a domain agent turns typed context into a data request and returns a typed result.

## Learning objectives

- Receive a typed `AgentRequest`.
- Build a domain-language question without embedding database schema knowledge.
- Access data through the injected MCP client.
- Normalize tool output into an `AgentResult`.
- Surface failures to the orchestrator.

## Build target

Complete the read path of the selected domain agent, including prompt construction, MCP invocation, payload normalization, and result construction.

## Lab activities

1. Review `AgentRequest`, `AgentResult`, and the domain-agent interface.
2. Build the domain-language MCP question from the user request and entities.
3. Invoke the injected MCP client.
4. Normalize returned rows into the agent's typed data shape.
5. Add a concise trace step.
6. Propagate MCP failures instead of returning false success.
7. Run the focused domain-agent tests.
8. Execute an end-to-end request through the completed pipeline.

## Success criteria

- The agent remains independent of database tables and columns.
- Successful tool output becomes a valid `AgentResult`.
- Tool failures terminate the orchestration path correctly.
