"""Probe (THROWAWAY): exercise CrewAgent end-to-end via MCP and print the result."""
import asyncio
import sys
import json
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent / "src"
sys.path.insert(0, str(SRC))

from app.config.config import Settings
from app.tools.mcp_client import McpClient
from app.agents.crew_agent import CrewAgent
from app.models.agent_request import AgentRequest
from app.models.entities import Entities


async def main():
    s = Settings.get_instance()
    mcp = McpClient(url=s.mcp_server_url, timeout=s.mcp_timeout, connect_timeout=s.mcp_connect_timeout)
    agent = CrewAgent(mcp_client=mcp)
    req = AgentRequest(agent="crew", entities=Entities())  # broad: find crews
    res = await agent.handle(req)
    print("=== CREW PROBE ===")
    print("success :", res.success)
    print("summary :", res.trace_step.summary)
    print("count   :", res.data.get("count"))
    print("question:", res.data.get("question"))
    print("sql     :", res.data.get("sql"))
    crews = res.data.get("crews") or []
    print("sample  :", json.dumps(crews[:3], indent=2, default=str)[:1200])


asyncio.run(main())