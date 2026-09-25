# Reliable Agents - Multi-Agent Workshop & Accelerator

<p align="center">
  <img src="https://img.shields.io/badge/Microsoft-Agent_Framework-0078D4?style=for-the-badge&logo=microsoft&logoColor=white" alt="Microsoft Agent Framework" />
  <img src="https://img.shields.io/badge/API-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Data-PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
</p>

Reliable Agents is a multi-agent system for operational asset-event response. A user asks a domain question in plain language; the application identifies the intent, creates and validates an execution plan, dispatches the request to authorized specialist agents, and assembles their structured results into one answer.

The current utility-focused implementation supports asset, event, crew, reliability, and customer questions. It is designed to demonstrate how models can propose intent and plans while deterministic code validates every step before execution. Operational data is accessed through a dedicated MCP service backed by PostgreSQL, and the browser receives live progress events as the workflow runs.

## UI Preview

<p align="center">
  <img src="docs/images/responseiq-ui.png" alt="Reliable Agents user interface placeholder" width="900" />
</p>

## Architecture

<p align="center">
  <img src="docs/images/responseiq-architecture.png" alt="Reliable Agents architecture diagram placeholder" width="900" />
</p>

```text
┌─────────────────────────┐       HTTP / NDJSON       ┌──────────────────────────┐
│ Static Browser UI       │ ◄───────────────────────► │ FastAPI Backend          │
│                         │                           │                          │
│ • Prompt library        │                           │ • Intent classification  │
│ • Response view         │                           │ • Plan validation        │
│ • Execution trace       │                           │ • Agent dispatch         │
│ • Asset map             │                           │ • Response assembly      │
└─────────────────────────┘                           └────────────┬─────────────┘
                                                                  │
                                                        validated │ typed objects
                                                                  ▼
                                                   ┌──────────────────────────┐
                                                   │ Plan-and-Execute         │
                                                   │ Reasoning                │
                                                   │                          │
                                                   │ Model proposes a plan;   │
                                                   │ code authorizes it       │
                                                   └────────────┬─────────────┘
                                                                │
                            ┌────────────┬────────────┬──────────┼───────────┐
                            ▼            ▼            ▼          ▼           ▼
                       ┌────────┐   ┌────────┐   ┌────────┐ ┌───────────┐ ┌──────────┐
                       │ Asset  │   │ Event  │   │ Crew   │ │Reliability│ │ Customer │
                       │ Agent  │   │ Agent  │   │ Agent  │ │ Agent     │ │ Agent    │
                       └───┬────┘   └───┬────┘   └───┬────┘ └───────────┘ └────┬─────┘
                           │            │            │                         │
                           └────────────┴────────────┴─────────────────────────┘
                                                  │ MCP
                                                  ▼
                                    ┌──────────────────────────┐
                                    │ MCP SQL Service          │
                                    │ • NL-to-SQL              │
                                    │ • PostgreSQL access      │
                                    └────────────┬─────────────┘
                                                 ▼
                                    ┌──────────────────────────┐
                                    │ PostgreSQL               │
                                    │ Operational data         │
                                    └──────────────────────────┘
```

## How It Works

1. The browser submits a user prompt to the FastAPI application.
2. The intent classifier returns a validated intent and typed domain entities.
3. The planner proposes an execution plan using only agents allowed for that intent.
4. Deterministic code rejects unknown agents, invalid dependencies, duplicate steps, dependency cycles, and plans over the step limit.
5. Approved specialist agents run in dependency order and return typed `AgentResult` objects.
6. MCP-backed agents query operational PostgreSQL data through the MCP SQL service.
7. The response assembler combines the results into a validated `ChatResult` and renders the final answer.
8. Intent, plan, agent-step, final, and error events stream to the UI as the workflow progresses.

### Key Design Decisions

- **Typed pipeline** - From intent recognition onward, every workflow hop uses validated Pydantic models rather than free-form text.
- **Deterministic authorization** - Models may propose intent and execution plans, but code controls which agents can run and validates the dependency graph first.
- **Bounded planning** - Plans are limited to eight steps and execute in validated topological order.
- **Specialist agents** - Asset, event, crew, reliability, and customer responsibilities are isolated behind a shared domain-agent contract.
- **MCP data boundary** - Database access is separated behind the MCP SQL service instead of being embedded in each agent.
- **Live instrumentation** - The UI shows intent, plan, and agent progress while the request is still running.
- **Observability** - OpenTelemetry instrumentation and Azure Monitor export support model, HTTP, and application diagnostics.

## Execution Trace

<p align="center">
  <img src="docs/images/responseiq-execution-trace.png" alt="Reliable Agents execution trace placeholder" width="900" />
</p>

## Project Structure

```text
reliable-agents-workshop/
├── .env.example                       # application configuration template
├── README.md                          # original project readme
├── README2.md                         # current Reliable Agents overview
├── AGENTS.md                          # repository development rules
├── pyproject.toml                     # Python project metadata
├── requirements.txt                   # backend dependencies
├── start                              # application startup wrapper
├── back                               # backend startup wrapper
├── front                              # frontend startup wrapper
├── mcp                                # MCP startup wrapper
├── inspect                            # MCP inspector wrapper
├── src/
│   ├── app/
│   │   ├── main.py                    # FastAPI composition root
│   │   ├── agents/                    # orchestrator and domain agents
│   │   ├── api/                       # HTTP and streaming routes
│   │   ├── config/                    # environment-driven settings
│   │   ├── identity/                  # Azure identity integration
│   │   ├── intent/                    # intent classification
│   │   ├── models/                    # typed Pydantic contracts
│   │   ├── observability/             # logging and telemetry
│   │   ├── orchestration/             # orchestration interfaces
│   │   ├── policy/                    # intent-to-agent authorization
│   │   ├── prompts/                   # Jinja prompt templates
│   │   ├── reasoning/                 # plan-and-execute reasoning
│   │   ├── services/                  # answer and map services
│   │   ├── state/                     # application state support
│   │   ├── tools/                     # MCP client and tool access
│   │   └── utils/                     # shared runtime utilities
│   ├── frontend/
│   │   ├── index.html                 # static application shell
│   │   ├── app.js                     # UI behavior and stream handling
│   │   ├── styles.css                 # application styling
│   │   ├── html/                      # supporting HTML content
│   │   └── images/                    # frontend assets
│   ├── mcp_sql/
│   │   ├── server.py                  # MCP HTTP server
│   │   ├── nl2sql.py                  # natural-language-to-SQL flow
│   │   ├── upstream.py                # pgEdge MCP integration
│   │   ├── config.py                  # MCP configuration
│   │   ├── telemetry.py               # MCP telemetry
│   │   ├── pyproject.toml             # isolated MCP dependencies
│   │   └── tests/                     # MCP tests
│   └── Dockerfile
├── scripts/
│   ├── bash/
│   │   ├── start-app.sh               # starts MCP, backend, and frontend
│   │   ├── start-backend.sh           # FastAPI on port 8010
│   │   ├── start-frontend.sh          # static UI on port 5500
│   │   └── start-mcp.sh               # MCP service on port 8000
│   ├── powershell/                    # Windows startup scripts
│   ├── cleanup/                       # process cleanup helpers
│   └── setup-secrets.sh               # local secret setup helper
├── tests/                              # backend tests and fixtures
├── data-generator/                     # synthetic utility-data generator
├── infra/                              # Azure deployment assets
├── docs2/                              # architecture, design, and specifications
└── docs/
    └── images/                         # README image drop location
```

## Prerequisites

The Python dependencies are defined in `requirements.txt` and `src/mcp_sql/pyproject.toml`.

| Tool or service            |                                      Version | Why it is needed                                                                                          |
| -------------------------- | -------------------------------------------: | --------------------------------------------------------------------------------------------------------- |
| Python                     |                                        3.11+ | Runs FastAPI, Agent Framework, MCP, tests, and the static frontend server                                 |
| PostgreSQL                 | Compatible server with the Reliable Agents schema | Stores operational asset, event, crew, reliability, and customer data                                     |
| Azure OpenAI               |                Endpoint plus deployed models | Runs intent classification, planning, response composition, and MCP NL-to-SQL                             |
| Azure CLI                  |                              Current version | Supplies local Azure credentials through `DefaultAzureCredential`; run `az login` first                   |
| pgEdge Postgres MCP binary |        Local executable under `src/mcp_sql/` | Provides the upstream PostgreSQL MCP tools used by the MCP SQL service                                    |
| macOS or Linux shell       |                                         Bash | Runs the included `scripts/bash/` launch scripts; PowerShell alternatives are under `scripts/powershell/` |

Key Python packages include FastAPI, Uvicorn, Microsoft Agent Framework, Pydantic, Azure Identity, OpenAI, Jinja2, HTTPX, OpenTelemetry, Azure Monitor exporter, pytest-asyncio, python-docx, and pypdf. The root application and MCP service intentionally use separate virtual environments.

## One-Time Setup

### 1. Create the backend environment

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### 2. Create the isolated MCP environment

```bash
cd src/mcp_sql
python3 -m venv .venv
.venv/bin/python -m pip install .
cd ../..
```

Do not install the MCP package into the root virtual environment. Its dependencies are intentionally isolated from the versions used by the FastAPI application.

### 3. Configure the application

Copy `.env.example` to `.env` and provide the environment-specific values:

```bash
cp .env.example .env
```

```env
AZURE_OPENAI_ENDPOINT=<azure-openai-endpoint>
INTENT_SML_DEPLOYMENT=<intent-and-planner-deployment>
INFERENCE_LM_DEPLOYMENT=<response-composition-deployment>
MCP_SERVER_URL=http://127.0.0.1:8000/mcp
APPLICATIONINSIGHTS_CONNECTION_STRING=<optional-application-insights-connection-string>
APP_ENVIRONMENT=dev
OPEN_SWAGGER_BROWSER=False
```

The settings layer accepts both `INTENT_SLM_DEPLOYMENT` and the legacy `INTENT_SML_DEPLOYMENT` spelling. The MCP SQL service has its own configuration under `src/mcp_sql/`; configure its PostgreSQL connection and model deployment separately.

### 4. Authenticate with Azure

```bash
az login
```

The application uses Azure identity credentials to obtain tokens for Azure OpenAI. API-key configuration is optional and is not required for the standard local flow.

## Daily Run

Start MCP, the backend, and the frontend together:

```bash
./start
```

The services run at:

| Component       | Address                     |
| --------------- | --------------------------- |
| Frontend        | `http://localhost:5500`     |
| FastAPI backend | `http://localhost:8010`     |
| MCP SQL service | `http://localhost:8000/mcp` |

The startup script waits for MCP before launching the backend and opens the browser after the frontend begins serving.

To run components separately:

```bash
./mcp
./back
./front
```

## Testing

Run the backend test suite from the repository root:

```bash
.venv/bin/python -m pytest -q
```

Run the isolated MCP test suite from its own environment:

```bash
cd src/mcp_sql
.venv/bin/python -m pytest -q
```

Live model, MCP, and database tests require valid Azure credentials and configured environment values.

## Tech Stack

| Layer         | Technology                                                                         |
| ------------- | ---------------------------------------------------------------------------------- |
| Frontend      | HTML, CSS, JavaScript, Fetch Streams                                               |
| Backend       | Python 3.11+, FastAPI, Uvicorn                                                     |
| Agent runtime | Microsoft Agent Framework                                                          |
| Models        | Azure OpenAI deployments                                                           |
| Contracts     | Pydantic                                                                           |
| Planning      | Structured plan generation plus deterministic validation and topological execution |
| Data access   | MCP, pgEdge Postgres MCP, PostgreSQL                                               |
| Identity      | Azure Identity / `DefaultAzureCredential`                                          |
| Prompting     | Jinja2 templates                                                                   |
| Streaming     | NDJSON over HTTP                                                                   |
| Observability | OpenTelemetry, Azure Monitor Application Insights exporter                         |
| Testing       | pytest, pytest-asyncio, HTTPX                                                      |

## Current Scope

Reliable Agents currently focuses on the typed operational-response pipeline: intent recognition, bounded plan generation, authorized specialist-agent execution, live instrumentation, and deterministic response assembly. Database durability beyond the connected operational store, retries, production authorization enforcement, and broader external tool integrations remain outside the current workshop-oriented scope.

## License

Internal use. See your organization's licensing policy.
