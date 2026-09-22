# Retry/backoff for startup scripts

## What it is

A resilience feature for `scripts/bash/start-app.sh`, the script that launches
MCP (`:8000`), the backend (`:8010`), and the frontend (`:5500`) together.
Today it starts all three, waits once for MCP/backend to answer, then polls
once a second to see if any of the three dies - and if one does, it just
prints which one died and stops watching. Nothing gets restarted automatically.

## What it will do

If a service (most likely MCP, since it's the one that's died so far) crashes
mid-session, the script would automatically try to restart just that service,
a bounded number of times, with a short delay between attempts - instead of
requiring the developer to notice the crash and manually re-run the whole
script.

## How it'd work

`start-app.sh` already does the pieces this needs:

- It backgrounds each service (`bash start-mcp.sh &` etc.) and keeps its PID.
- It already has a polling loop (`kill -0 "$PID"`) checking once a second
  whether each PID is still alive.

The extension: instead of the polling loop just printing "X died" and
`break`-ing out, it would call that service's own `start-*.sh` again in the
background, capture the new PID, and keep watching - retrying a capped number
of times (e.g. 3) with a short backoff between attempts (e.g. 1s, 2s, 4s), and
only then printing a final "gave up after N attempts" message if it keeps
failing.

## How we'd implement it

- Track a per-service restart counter (`MCP_RESTARTS=0`, `BACKEND_RESTARTS=0`, etc.).
- Replace each `if ! kill -0 "$X_PID"` branch in the existing polling loop with:
  restart counter check -> if under the cap, sleep (backoff), re-run
  `start-mcp.sh`/`start-backend.sh` in the background, capture the new PID,
  increment the counter, `continue` the loop instead of `break`-ing.
- Keep the loud, distinct print for the "gave up" case, so a persistent crash
  (e.g. bad `DATABASE_URL`, a code exception on every request) still surfaces
  clearly instead of silently crash-looping forever.
- Scope: bash-only change, one file (`start-app.sh`). No changes to the
  Python app, MCP server, or frontend.

## Business Value

Reduces friction during live demos/workshops if a transient startup race (like
the one that prompted this doc - MCP died once during `start-app.sh`, backend
kept running, `/map/assets` failed with a 502 until the developer noticed and
manually restarted MCP) happens again. Saves a manual "notice it's down, go
restart it" step during a live session.

Explicitly scoped as a **local dev/demo convenience**, not a production
process supervisor (systemd, container restart policies, etc.) - this app
doesn't run in a context where that distinction matters yet, but it's worth
naming so nobody mistakes this for real operational resilience later.

## Discussion Notes

- Triggering incident (2026-09-20 morning): `start-app.sh` showed
  `MCP (:8000) died - scroll up for its traceback`, and the backend's own log
  showed a `ConnectError: All connection attempts failed` when
  `MapAssetService` tried to reach MCP. Re-running `bash scripts/bash/start-mcp.sh`
  directly started it cleanly with no errors - looked like a one-off startup
  race (MCP and backend launching close together), not a reproducible bug in
  MCP itself.
- Decision: not building this now. Reasoning discussed and agreed:
  - This is the first time it's happened - not yet a recurring pattern worth
    the added complexity.
  - Auto-restart carries real tradeoffs, not just added code:
    1. **Can mask real bugs.** A persistent failure (bad DB creds, a genuine
       code exception) would crash-loop instead of surfacing once, clearly -
       needs a hard cap + loud "gave up" message to avoid becoming _harder_
       to debug, not easier.
    2. **Session loss on restart.** MCP is stateless per-call (verified in
       `mcp_client.py`'s own docstring: "each query() opens and closes its OWN
       session as a local"), so restarting it mid-use is harmless. The
       backend is not stateless - an in-progress conversation
       (`conversation_id`, in-memory state) would be lost if the backend
       itself auto-restarted mid-session, with no warning to whoever's using
       the UI at that moment.
    3. **This is a dev convenience script, not a supervisor** - "it crashed,
       re-run `start-app.sh`" is an acceptable manual fallback for a
       local/demo tool, at least until this becomes a repeat problem.
  - Revisit if this recurs more than a couple of times, or before this app is
    ever run in a context where nobody's watching the terminal live.
