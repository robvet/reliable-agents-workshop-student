# mcp_sql — Phase 0 POC

Remote MCP server (`run_sql`, `ask`) over an Azure Postgres Flexible Server,
via the pgEdge Postgres MCP binary as a stdio subprocess. Disposable sandbox -
not production code (see `AGENTS.md`'s `src/mcp_sql/` exception section).

## Run it

```bash
cd src/mcp_sql
python3 -m venv .venv
source .venv/bin/activate
pip install .
cp .env.example .env   # fill in real values
python3 server.py      # Streamable HTTP on http://0.0.0.0:8000/mcp
```

Point MCP Inspector (or any Streamable HTTP MCP client) at
`http://localhost:8000/mcp`.

## Env vars

| Var                                     | Purpose                                                                                            |
| --------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`                          | Single source of truth for the Postgres connection. Parsed and passed to pgEdge via `PGEDGE_DB_*`. |
| `MCP_OPENAI_ENDPOINT`                   | Azure AI Foundry endpoint for the one `ask` LLM call.                                              |
| `INFERENCE_LM_DEPLOYMENT`               | Model/deployment name for that call.                                                               |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Optional. Server runs and logs to stdout without it.                                               |
| `MAX_ROWS`                              | Row cap per call. Default 100.                                                                     |
| `PGEDGE_BIN`                            | Path to the pgedge-postgres-mcp binary. Default `./pgedge-postgres-mcp`.                           |
| `PGEDGE_CONFIG`                         | Only needed if `PGEDGE_*` env vars don't work (they did here — see below).                         |

No `MCP_OPENAI_API_KEY` — auth is AAD (`DefaultAzureCredential`), no static key.

## `tools/list` (real output, Task 1, pgedge-postgres-mcp v1.0.0, darwin_arm64)

```
generate_embedding
query_database
get_schema_info
similarity_search
execute_explain
count_rows
read_resource
```

We use `query_database` (wrapped by `run_sql`) and `get_schema_info` (feeds
`ask`'s prompt). The rest are ignored per spec scope.

## Env vars vs. YAML

**Env vars won.** `PGEDGE_DB_HOST/PORT/NAME/USER/PASSWORD/SSLMODE/ALLOW_WRITES`
built from `DATABASE_URL` connected on the first try — no YAML rendering
needed. `vendor/examples/pgedge-postgres-mcp-custom.yaml` (bundled with the
release, not the `-stdio.yaml.example` file the spec expected — pgEdge's own
naming) is untouched.

## pgEdge vs. asyncpg

Stayed on pgEdge. It connected cleanly in Task 1; the asyncpg fallback in the
spec's Task 1 timebox note was never triggered.

## Where traces land

Application Insights, via `azure-monitor-opentelemetry`'s
`configure_azure_monitor(connection_string=...)` in `telemetry.py` — the
connection string is passed **explicitly**, not left to ambient env-var
pickup (confirmed necessary in Task 2). One span + one `tool_call` log line
per `run_sql`/`ask` call, with `tool`, `sql`, `row_count`, `elapsed_ms`,
`outcome`. Nothing prints to stdout by default; allow 1–2 minutes for
batched export. If `APPLICATIONINSIGHTS_CONNECTION_STRING` is unset, the
server still starts and both tools still work — telemetry is never a
startup dependency.

## Dependency deviations from the spec's pin list

The spec pins `openai` for the `ask` LLM call. We use **`agent-framework`**
(`agent_framework.openai.OpenAIChatClient`) + **`azure-identity`** instead,
per explicit direction: reuse the exact client-construction pattern already
used by `src/app/agents/gpt_agent.py` (Azure OpenAI Responses API,
`DefaultAzureCredential` + `get_bearer_token_provider`, no static API key).
`MCP_OPENAI_API_KEY` / `MCP_OPENAI_MODEL` were dropped from the env var list;
`INFERENCE_LM_DEPLOYMENT` is used instead of `MCP_OPENAI_MODEL`. See
`src/mcp_sql/pyproject.toml` and `nl2sql.py`.

`mcp_sql` has its own venv (`src/mcp_sql/.venv`), separate from the repo root's
`.venv` — its dependencies (and any future version bumps) must never be
installed into the shared root venv, which pins specific OpenTelemetry
versions for `src/app`.

## Phase 0 limitations

- No `UpstreamAdapter`, no mock/swappable backend — pgEdge only.
- No auth on our own endpoint, no Entra ID/managed identity/Key Vault for it.
- No writes: `allow_writes` stays `false`, enforced upstream by pgEdge itself
  (our `check()` guard in `server.py` is a fast-fail convenience, not the
  security boundary).
- Single database, no multi-host/failover.
- No caching beyond the lazily-fetched, in-memory schema cache for `ask`
  (fetched on first `ask()` call, not at startup; not persisted, not shared
  across processes).
- No retries, no multi-step reasoning — `ask` is one LLM call; a bad
  generated SQL statement is reported back as `{sql, error}`, not retried.
- No streaming — one response per call.
- `query_database` returns a plain tab-separated **text** report, not JSON —
  all cell values come back as strings, and `NULL` is indistinguishable from
  an empty string (see `upstream.py`).
- No frontend/UI — MCP Inspector and `pytest` only.
