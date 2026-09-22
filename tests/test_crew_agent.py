from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.crew_agent import CrewAgent
from app.models.agent_request import AgentRequest
from app.models.entities import Entities


class TestCrewAgent:
    @pytest.mark.asyncio
    async def test_preserves_user_request_and_mcp_result(self) -> None:
        user_prompt = (
            "Compare crew response times from the last seven days, "
            "excluding cancelled assignments."
        )
        mcp_client = MagicMock()
        mcp_client.query = AsyncMock(return_value={
            "rows": [{"region": "north", "minutes": 18}],
            "sql": "SELECT region, AVG(response_minutes)",
            "reasoning": "Compared completed crew responses.",
        })

        result = await CrewAgent(mcp_client).handle(AgentRequest(
            agent="crew",
            user_prompt=user_prompt,
        ))

        question = mcp_client.query.await_args.args[0]
        assert user_prompt in question
        assert "current assignments and estimated time of arrival" not in question
        assert "For each crew return" not in question
        assert result.data == {
            "crews": [{"region": "north", "minutes": 18}],
            "count": 1,
            "sql": "SELECT region, AVG(response_minutes)",
            "question": question,
            "reasoning": "Compared completed crew responses.",
        }

    def test_appends_typed_crew_filters(self) -> None:
        agent = CrewAgent(MagicMock())
        question = agent._build_prompt(AgentRequest(
            agent="crew",
            user_prompt="Show the relevant crews",
            entities=Entities(
                event_id="OUT-9",
                asset_id="TX-17",
                feeder="F-3",
                substation="Central",
                location="north region",
            ),
        ))

        assert question == (
            "Answer the crew portion of this request: Show the relevant crews "
            "Use these extracted values as required filters: outage OUT-9, asset TX-17, "
            "feeder F-3, substation Central, location north region."
        )

    def test_preserves_context_added_to_user_prompt(self) -> None:
        agent = CrewAgent(MagicMock())
        question = agent._build_prompt(AgentRequest(
            agent="crew",
            user_prompt=(
                "Which crews are handling those outages?\n\n"
                'Results from agents that already completed this request:\n'
                '{"event": {"events": [{"outage_id": "OUT-9"}]}}'
            ),
        ))

        assert question == (
            "Answer the crew portion of this request: Which crews are handling those outages?\n\n"
            "Results from agents that already completed this request:\n"
            '{"event": {"events": [{"outage_id": "OUT-9"}]}}'
        )