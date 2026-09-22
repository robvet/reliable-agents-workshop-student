#!/bin/bash
# Start the mcp_sql MCP server (disposable POC sandbox — see AGENTS.md).
#
# Deliberately does NOT use the repo root .venv. mcp_sql has its own venv at
# src/mcp_sql/.venv, and its dependencies must never be installed into the
# shared root venv (which pins specific OpenTelemetry versions for src/app).

set -e

# Run from src/mcp_sql: the pgEdge binary path and the .env lookup are both CWD-relative.
cd "$(dirname "${BASH_SOURCE[0]}")/../../src/mcp_sql"

[ -x .venv/bin/python ] || { echo "No mcp_sql venv. Run: cd src/mcp_sql && python3 -m venv .venv && .venv/bin/python -m pip install ."; exit 1; }
[ -x ./pgedge-postgres-mcp ] || { echo "pgedge-postgres-mcp missing or not executable in src/mcp_sql"; exit 1; }

# Free our own port. -sTCP:LISTEN matches only the process LISTENING on 8000, not clients
# that merely hold a connection to it.
lsof -ti:8000 -sTCP:LISTEN 2>/dev/null | xargs -r kill
sleep 1

echo -e "\033[36mMCP      -> http://localhost:8000/mcp\033[0m"
# Its own venv, called directly. Never activate - that is how root deps leak in here.
exec .venv/bin/python server.py
