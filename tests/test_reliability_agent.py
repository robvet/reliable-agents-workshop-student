from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.reliability_agent import ReliabilityAgent
from app.models.agent_request import AgentRequest
from app.models.entities import Entities


class TestReliabilityAgent:
    @pytest.mark.asyncio
    async def test_preserves_user_request_and_mcp_result(self) -> None:
        user_prompt = "Compare repeat equipment failures by asset during the last year."
        mcp_client = MagicMock()
        mcp_client.query = AsyncMock(return_value={
            "rows": [{"asset_id": "TX-17", "failure_count": 3}],
            "sql": "SELECT asset_id, COUNT(*)",
            "reasoning": "Counted equipment failures by asset.",
        })

        result = await ReliabilityAgent(mcp_client).handle(AgentRequest(
            agent="reliability",
            user_prompt=user_prompt,
        ))

        question = mcp_client.query.await_args.args[0]
        assert user_prompt in question
        assert "saidi_minutes" not in question
        assert result.data == {
            "reliability": [{"asset_id": "TX-17", "failure_count": 3}],
            "count": 1,
            "sql": "SELECT asset_id, COUNT(*)",
            "question": question,
            "reasoning": "Counted equipment failures by asset.",
        }

    def test_appends_typed_reliability_filters(self) -> None:
        question = ReliabilityAgent(MagicMock())._build_prompt(AgentRequest(
            agent="reliability",
            user_prompt="Show the relevant reliability history",
            entities=Entities(
                asset_id="TX-17",
                feeder="F-3",
                substation="Central",
                event_id="OUT-9",
                location="north region",
            ),
        ))

        assert question == (
            "Answer the reliability portion of this request: Show the relevant reliability history "
            "Use these extracted values as required filters: asset TX-17, feeder F-3, "
            "substation Central, outage OUT-9, location north region."
        )

    def test_preserves_context_added_to_user_prompt(self) -> None:
        question = ReliabilityAgent(MagicMock())._build_prompt(AgentRequest(
            agent="reliability",
            user_prompt=(
                "Assess the reliability of those assets.\n\n"
                "Results from agents that already completed this request:\n"
                '{"asset": {"assets": [{"asset_id": "TX-17"}]}}'
            ),
        ))

        assert question == (
            "Answer the reliability portion of this request: Assess the reliability of those assets.\n\n"
            "Results from agents that already completed this request:\n"
            '{"asset": {"assets": [{"asset_id": "TX-17"}]}}'
        )