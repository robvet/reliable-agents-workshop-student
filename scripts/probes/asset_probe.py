
"""Probe (THROWAWAY): exercise AssetAgent end-to-end via MCP and print the result."""
import asyncio
import sys
import json
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent / "src"
sys.path.insert(0, str(SRC))

from app.config.config import Settings
from app.tools.mcp_client import McpClient
from app.agents.asset_agent import AssetAgent
from app.models.agent_request import AgentRequest
from app.models.entities import Entities


async def main():
    s = Settings.get_instance()
    mcp = McpClient(url=s.mcp_server_url, timeout=s.mcp_timeout, connect_timeout=s.mcp_connect_timeout)
    agent = AssetAgent(mcp_client=mcp)
    req = AgentRequest(agent="asset", entities=Entities())  # broad: find assets
    res = await agent.handle(req)
    print("=== ASSET PROBE ===")
    print("success :", res.success)
    print("summary :", res.trace_step.summary)
    print("count   :", res.data.get("count"))
    print("question:", res.data.get("question"))
    print("sql     :", res.data.get("sql"))
    assets = res.data.get("assets") or []
    print("sample  :", json.dumps(assets[:3], indent=2, default=str)[:1200])


asyncio.run(main())