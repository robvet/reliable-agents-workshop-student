#!/bin/bash
# Starts all three servers. Ctrl+C stops all three.
#
# Each start-*.sh below frees its own port and picks its own python, so all this script
# has to do is launch them and shut them down.
set -e

cd "$(dirname "${BASH_SOURCE[0]}")"

# Stop everything with one signal.
#
# uvicorn --reload runs its worker in a CHILD process, so signalling only the pids we
# started here misses it. That worker survived as an orphan still holding :8010, which is
# why the next launch had to SIGKILL it - the "Killed: 9" line. Everything started below
# inherits our process group, and signalling the whole group reaches the worker too.
# Verified on this machine: uvicorn's parent and its reload worker share one pgid.
PGID="$(ps -o pgid= -p $$ | tr -d ' ')"
trap 'trap - EXIT; echo; echo "Stopping..."; kill -- "-$PGID" 2>/dev/null' EXIT

bash start-mcp.sh &
MCP_PID=$!

# The backend calls MCP immediately when the frontend loads map assets. Wait until
# MCP accepts HTTP connections instead of assuming it starts within a fixed delay.
MCP_DEADLINE=$((SECONDS + 20))
while (( SECONDS < MCP_DEADLINE )); do
    curl -s -o /dev/null --max-time 0.5 http://127.0.0.1:8000/mcp && MCP_READY=1 && break
    sleep 0.5
done

if [ -z "$MCP_READY" ]; then
    echo -e "\033[31mMCP never answered on :8000 after 20s - scroll up for its traceback.\033[0m"
    exit 1
fi

bash start-backend.sh &
BACKEND_PID=$!
bash start-frontend.sh &
FRONTEND_PID=$!

# Wait until the backend actually answers, up to 20s. Printing "started" and walking away
# is how a backend that died on startup used to show up as a UI that silently fetched nothing.
for _ in $(seq 40); do
    curl -sf -o /dev/null --max-time 2 http://127.0.0.1:8010/prompt-library && READY=1 && break
    sleep 0.5
done

echo ""
if [ -n "$READY" ]; then
    echo -e "\033[36mAll three up. Ctrl+C to stop.\033[0m"
else
    echo -e "\033[31mBackend never answered on :8010 - scroll up for its traceback.\033[0m"
fi

# Same silent-failure problem as above, but mid-session: if one of the three dies later
# (crash, unhandled exception, OOM), the other two keep running and nothing calls that
# out - the UI just starts failing fetches with no clue why. Poll each PID and name the
# one that died the moment it does, instead of leaving it to be discovered via curl.
# Bash on macOS is 3.2 (no `wait -n`), so a poll loop is what's portable here.
while true; do
    if ! kill -0 "$MCP_PID" 2>/dev/null; then
        echo -e "\033[31mMCP (:8000) died - scroll up for its traceback.\033[0m"
        break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo -e "\033[31mBackend (:8010) died - scroll up for its traceback.\033[0m"
        break
    fi
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo -e "\033[31mFrontend (:5500) died - scroll up for its traceback.\033[0m"
        break
    fi
    sleep 1
done

# Block here, or the script would exit immediately and Ctrl+C would have nothing to interrupt.
wait
