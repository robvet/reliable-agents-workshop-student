from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.asset_agent import AssetAgent
from app.models.agent_request import AgentRequest
from app.models.entities import Entities


class TestAssetAgent:
    @pytest.mark.asyncio
    async def test_preserves_user_request_and_mcp_result(self) -> None:
        user_prompt = (
            "How many transformers were inspected in the last 30 days, "
            "excluding retired assets?"
        )
        mcp_client = MagicMock()
        mcp_client.query = AsyncMock(return_value={
            "rows": [{"count": 12}],
            "sql": "SELECT COUNT(*)",
            "reasoning": "Counted recent non-retired transformers.",
        })

        result = await AssetAgent(mcp_client).handle(AgentRequest(
            agent="asset",
            user_prompt=user_prompt,
        ))

        question = mcp_client.query.await_args.args[0]
        assert user_prompt in question
        assert "For each asset return" not in question
        assert result.data == {
            "assets": [{"count": 12}],
            "count": 1,
            "sql": "SELECT COUNT(*)",
            "question": question,
            "reasoning": "Counted recent non-retired transformers.",
        }

    def test_appends_typed_asset_filters(self) -> None:
        agent = AssetAgent(MagicMock())
        question = agent._build_prompt(AgentRequest(
            agent="asset",
            user_prompt="Show the assets involved in this incident",
            entities=Entities(
                asset_id="TX-17",
                feeder="F-3",
                substation="Central",
                location="north region",
            ),
        ))

        assert question == (
            "Answer the asset portion of this request: Show the assets involved in this incident "
            "Scope the query starting from: asset TX-17, feeder F-3, substation Central, "
            "location north region. If the request asks about assets affected, impacted, or "
            "downstream of that starting point (e.g. due to an outage), that starting asset is "
            "the ROOT of the traversal, not an exact-match filter - include it and everything "
            "downstream of it. Only treat it as an exact-match filter (return just that one "
            "asset) when the request is asking about the asset itself with no "
            "affected/impacted/downstream framing. "
            "Reference (fixed schema, not live data): grid_assets.asset_type allows "
            "SUBSTATION, FEEDER, TRANSFORMER; grid_assets.asset_condition (lifecycle - is the "
            "asset commissioned and in service?) allows INSTALLED, MAINTENANCE, RETIRED; "
            "grid_assets.status (real-time outage state, kept in sync automatically) allows "
            "REPORTED, CONFIRMED, CREW_ASSIGNED, RESTORED, NORMAL - NORMAL means no open "
            "outage. If the question asks what values a column CAN or MAY hold, answer from "
            "this reference instead of querying current rows."
        )