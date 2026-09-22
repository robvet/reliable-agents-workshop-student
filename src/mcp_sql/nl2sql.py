"""nl2sql.py — the only module in mcp_sql that talks to an LLM.

Flat module, one function: to_sql(question, schema) -> str. One LLM call,
no retries, no validation loop. If the LLM writes bad SQL, that's the
caller's (server.py's) problem to report — this module doesn't judge it.

Client construction mirrors src/app/agents/gpt_agent.py: agent_framework's
OpenAIChatClient over Azure OpenAI's Responses API, authenticated via
DefaultAzureCredential + get_bearer_token_provider (AAD, no API key). Read
that file for the pattern; it is not imported or modified here — mcp_sql
must stay independently runnable.
"""

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from pathlib import Path

from config import inference_lm_deployment, mcp_openai_endpoint

_PROMPT_PATH = Path(__file__).with_name("prompts").joinpath("nl2sql.system.txt")
_INSTRUCTIONS = _PROMPT_PATH.read_text(encoding="utf-8").strip()

# Built once at import time. DefaultAzureCredential only ASSEMBLES a credential
# chain here; no network call happens until the first actual completion.
_credential = DefaultAzureCredential()
_token_provider = get_bearer_token_provider(_credential, "https://cognitiveservices.azure.com/.default")

_client = OpenAIChatClient(
    azure_endpoint=mcp_openai_endpoint(),
    model=inference_lm_deployment(),
    credential=_token_provider,
)

_agent = Agent(
    client=_client,
    name="nl2sql",
    instructions=_INSTRUCTIONS,
    default_options={
        # Ask a reasoning model (GPT-5-class) for a summary of how it built the SQL.
        "reasoning": {"effort": "medium", "summary": "detailed"},
        "store": False,
    },
)


def _extract_text(raw_response: object) -> str:
    """Extract text from an AF response across provider-specific shapes.

    Copied from src/app/agents/gpt_agent.py's _extract_af_text — same AF
    response shapes apply here.
    """
    if isinstance(raw_response, str):
        return raw_response.strip()

    value = getattr(raw_response, "text", None)
    if isinstance(value, str) and value:
        return value.strip()

    value = getattr(raw_response, "content", None)
    if isinstance(value, str) and value:
        return value.strip()

    contents = getattr(raw_response, "contents", None)
    if isinstance(contents, list):
        parts = []
        for part in contents:
            part_text = getattr(part, "text", getattr(part, "content", None))
            if isinstance(part_text, str) and part_text:
                parts.append(part_text)
        if parts:
            return "\n".join(parts).strip()

    return str(raw_response).strip()


def _strip_fences(text: str) -> str:
    """Strip a markdown code fence the model may add despite instructions."""
    s = text.strip()
    if s.startswith("```"):
        lines = s.splitlines()[1:]  # drop opening fence, incl. any language tag
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def _extract_reasoning(raw_response: object) -> str:
    """Pull the model's reasoning-summary text from the response (telemetry only).

    Mirrors the intent classifier: reasoning models return a distilled SUMMARY of
    their hidden chain-of-thought as `text_reasoning` content parts (never the raw
    tokens). We collect those summary parts; the SQL answer comes from _extract_text.
    """
    parts: list[str] = []
    saw_reasoning_item = False
    for message in getattr(raw_response, "messages", None) or []:
        for content in getattr(message, "contents", None) or []:
            if getattr(content, "type", None) == "text_reasoning":
                saw_reasoning_item = True
                text = getattr(content, "text", "") or ""
                if text:
                    parts.append(text)
    if parts:
        return "\n".join(parts)
    if saw_reasoning_item:
        return "Reasoning summary was withheld by the model/runtime for this call."
    return ""


async def to_sql(question: str, schema: str) -> tuple[str, str]:
    """Generate a single read-only SQL statement plus the model's reasoning summary."""
    prompt = f"Schema:\n{schema}\n\nQuestion: {question}"
    raw_response = await _agent.run(prompt)
    sql = _strip_fences(_extract_text(raw_response))
    reasoning = _extract_reasoning(raw_response)
    return sql, reasoning
