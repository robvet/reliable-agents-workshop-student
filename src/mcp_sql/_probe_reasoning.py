"""THROWAWAY probe: does gpt-5.6-sol accept reasoning effort=high, and what
reasoning shape comes back? Mirrors nl2sql.py's client construction exactly.

Run from src/mcp_sql with its venv active:  python _probe_reasoning.py
Delete after use.
"""
import asyncio

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from config import inference_lm_deployment, mcp_openai_endpoint
from nl2sql import _extract_reasoning, _extract_text, _strip_fences

_SCHEMA = (
    "Table outages(outage_id uuid, affected_asset uuid, status text, "
    "start_time timestamptz, estimated_restoration timestamptz, impact_count int)\n"
    "Table grid_assets(asset_id uuid, asset_name text, asset_type text, parent_asset uuid, region text)"
)
_QUESTION = (
    "Find outages that are still active (not yet restored or closed) on feeder Feeder-100. "
    "Return each outage's id, affected asset, status, start time, estimated restoration, "
    "and how many are impacted."
)

_credential = DefaultAzureCredential()
_token_provider = get_bearer_token_provider(_credential, "https://cognitiveservices.azure.com/.default")
_client = OpenAIChatClient(
    azure_endpoint=mcp_openai_endpoint(),
    model=inference_lm_deployment(),
    credential=_token_provider,
)


def _dump_shape(raw) -> None:
    for mi, message in enumerate(getattr(raw, "messages", None) or []):
        for ci, content in enumerate(getattr(message, "contents", None) or []):
            ctype = getattr(content, "type", None)
            text = getattr(content, "text", None)
            has = bool(text and text.strip())
            print(f"    msg[{mi}].content[{ci}] type={ctype!r} has_text={has}")


async def _run(effort: str) -> None:
    print(f"\n==== effort={effort} model={inference_lm_deployment()} ====")
    agent = Agent(
        client=_client,
        name="probe",
        instructions="You write one read-only PostgreSQL SELECT that answers the question. Output only SQL.",
        default_options={
            "reasoning": {"effort": effort, "summary": "detailed"},
            "store": False,
        },
    )
    prompt = f"Schema:\n{_SCHEMA}\n\nQuestion: {_QUESTION}"
    try:
        raw = await agent.run(prompt)
    except Exception as e:  # noqa: BLE001 - probe wants the raw error text
        print(f"  REJECTED/ERROR: {type(e).__name__}: {e}")
        return
    sql = _strip_fences(_extract_text(raw))
    reasoning = _extract_reasoning(raw)
    print(f"  SQL: {sql[:200]}")
    print(f"  reasoning_len={len(reasoning)} reasoning_head={reasoning[:120]!r}")
    print("  response shape:")
    _dump_shape(raw)


async def main() -> None:
    for effort in ("medium", "high"):
        await _run(effort)


if __name__ == "__main__":
    asyncio.run(main())
