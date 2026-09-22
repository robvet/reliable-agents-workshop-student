# How the Application Runs

Understand which components run locally, which services run in Azure, and how requests cross those boundaries.

## Learning objectives

- Identify where the frontend, backend, MCP server, models, and database run.
- Trace a request from the browser to the final response.
- Distinguish model decisions from deterministic application control.
- Distinguish the read-only data path from the deterministic write path.

## Component responsibilities

This section will describe the execution location and responsibility of each component:

- Web frontend
- FastAPI backend
- Deterministic orchestrator
- Azure-hosted model deployments
- MCP and natural-language-to-SQL process
- PostgreSQL

## Request flow

This section will trace classification, reasoning, validated dispatch, domain-agent execution, response assembly, and streaming results.

## Data-access boundaries

This section will compare the read-only MCP path with the direct, deterministic outage lifecycle write path.

## Knowledge check

Students will identify where each operation executes and which component enforces its authorization or security boundary.
