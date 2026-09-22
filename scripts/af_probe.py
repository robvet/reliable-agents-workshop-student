"""Slice 0 probe (THROWAWAY): verify AF OpenAIChatClient (Responses API) against Azure OpenAI.

Proves, end-to-end: agent_framework OpenAIChatClient -> Responses API -> Reliable Agents'
Azure OpenAI endpoint -> app managed-identity auth, for BOTH plain and structured output.
Delete this file once it passes.
"""
import asyncio
import sys
from pathlib import Path

from pydantic import BaseModel

# Make the app package importable when run from the repo root.
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from agent_framework import ChatOptions
from agent_framework.openai import OpenAIChatClient

from app.config.config import Settings
from app.identity.azure_identity_provider import AzureIdentityProvider


class Probe(BaseModel):
    """Tiny structured-output target."""
    word: str


async def main() -> None:
    settings = Settings.get_instance()
    identity = AzureIdentityProvider.default()

    client = OpenAIChatClient(
        azure_endpoint=settings.azure_openai_endpoint,
        model=settings.azure_openai_deployment_gpt,
        credential=identity.token_provider,
    )
    agent = client.as_agent(instructions="You reply tersely and exactly as asked.")

    # 1) Plain text
    plain = await agent.run("Reply with the single word: pong")
    print("PLAIN   .text  ->", repr(plain.text))

    # 2) Structured output (schema-enforced via Pydantic)
    structured = await agent.run(
        "Return the word 'pong'.",
        options=ChatOptions(response_format=Probe),
    )
    print("STRUCT  .value ->", structured.value, "| type:", type(structured.value).__name__)


if __name__ == "__main__":
    asyncio.run(main())
