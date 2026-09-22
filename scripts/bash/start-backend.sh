#!/bin/bash
# Start the Python backend server

set -e

# Run from the repo root: uvicorn resolves --app-dir relative to the current directory.
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

[ -x .venv/bin/python ] || { echo "No .venv here. Run: python3 -m venv .venv"; exit 1; }

# Free our own port. -sTCP:LISTEN matches only the process LISTENING on 8010. Without it
# lsof also lists browsers and curl that merely hold a connection, and we would kill those.
# Plain kill is SIGTERM, so the server can close its socket and reap its children.
lsof -ti:8010 -sTCP:LISTEN 2>/dev/null | xargs -r kill
sleep 1

echo -e "\033[36mBackend  -> http://localhost:8010\033[0m"
# Call .venv/bin/python straight out - no activate, no deactivate, no PATH juggling.
# exec replaces this shell with uvicorn, so there is no extra process in the way.
exec .venv/bin/python -m uvicorn app.main:create_app --factory \
    --host 127.0.0.1 --port 8010 --app-dir src
