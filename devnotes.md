# Dev Notes

## create virtual environment (.venv) with python 3.11

python3.11 -m venv .venv

## activate venv

source .venv/bin/activate

## robvet subscription commands

az account set --subscription "ME-MngEnvMCAP659660-robvet-1"
az account set --subscription "ME-MngEnvMCAP190177-robvet-1"

## Install requirements

pip install -r requirements.txt

## create .tom; file from requirements.txt

python -m pip install -e ".[dev]"
pip install -e ".[dev]"

## start app:

Ports:

- MCP -> http://localhost:8000/mcp
- Frontend -> http://localhost:5500
- Backend -> http://localhost:8010

./start (start backend and mcp)
./mcp (start mcp server)
./front
./back
./inspect (start MCP inspector)

cd src/frontend && python3 -m http.server 5500
http://127.0.0.1:5500

python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8010 --app-dir src

## synthetic data generator

cd data-generator
./.venv/bin/streamlit run utility-data-generator.py --server.port 8501

When configuring uvicorn in Azure, the `--app-dir src` flag is required so uvicorn can
locate the `app` module. Use this as the startup command:

## Intent Testing

UNKNOWN:
"where is Los Angeles?"

Crew"
Dispatch a crew to restore the outage on feeder F-12
What crews are assigned to the substation outage?'

"Asset"
Prompt: How many assets are impacted by the major storm event across the north region?
Expected Intent: MAJOR_EVENT
Agents Dispatched: event, asset

"Event"
Prompt: Give me a status summary of all active outages right now.
Expected Intent: SITUATIONAL_AWARENESS
Agents Dispatched: event, crew

"Reliabilty:"
Prompt: What's the failure history and reliability score for transformer T-238?
Expected Intent: RELIABILITY
Agents Dispatched: reliability, asset

"MultiAgent Response"
Prompt: Dispatch a crew to restore the outage on feeder F-12 and tell me which assets are affected.
Prompt: Find outages that are still active in the north region. Return each outage id and affected asset
Prompt: Dispatch a crew to restore the outage on feeder F-12
Prompt: Give me a status summary of ongoing outages and crews in the West region" \ "Which assets and active events are affecting the East region right now?

```
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --app-dir src
```

> Note: Azure uses port `8000` by default. The local dev port is `8010`.

## start frontend

python -m streamlit run src/ui/streamlit_app.py

=========================================

## Environment Variables

`pydantic_settings` resolves configuration values in the following priority order:

1. **Actual environment variables** (highest priority)
2. `.env` file (local fallback)
3. Field defaults (lowest priority)

In Azure (App Service, Container Apps, etc.), set all values as **Application Settings**.
These become real environment variables at runtime — pydantic reads them directly and never
looks for a `.env` file. If the file is absent, it is silently skipped with no error.

The `.env` file is for **local development only** and should never be committed to source control.

---

## Checklist

- [ ] All `.env` values added as Application Settings in Azure portal (or via `az cli` / Bicep)
- [ ] Startup command includes `--app-dir src`
- [ ] `.env` confirmed in `.gitignore`
