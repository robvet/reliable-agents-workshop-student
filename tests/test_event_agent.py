from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.event_agent import EventAgent
from app.models.agent_request import AgentRequest
from app.models.entities import Entities


class TestEventAgent:
    @pytest.mark.asyncio
    async def test_preserves_user_request_and_mcp_result(self) -> None:
        user_prompt = (
            "Compare restored and unresolved outages from the last 24 hours, "
            "excluding planned maintenance."
        )
        mcp_client = MagicMock()
        mcp_client.query = AsyncMock(return_value={
            "rows": [{"status": "unresolved", "count": 3}],
            "sql": "SELECT status, COUNT(*)",
            "reasoning": "Compared outage statuses.",
        })

        result = await EventAgent(mcp_client).handle(AgentRequest(
            agent="event",
            user_prompt=user_prompt,
        ))

        question = mcp_client.query.await_args.args[0]
        assert user_prompt in question
        assert "still active" not in question
        assert "Return each outage" not in question
        assert result.data == {
            "events": [{"status": "unresolved", "count": 3}],
            "count": 1,
            "question": question,
            "sql": "SELECT status, COUNT(*)",
            "reasoning": "Compared outage statuses.",
        }

    def test_appends_typed_event_filters(self) -> None:
        agent = EventAgent(MagicMock())
        question = agent._build_prompt(AgentRequest(
            agent="event",
            user_prompt="Show the relevant outages",
            entities=Entities(
                asset_id="TX-17",
                feeder="F-3",
                substation="Central",
                event_id="OUT-9",
                location="north region",
            ),
        ))

        assert question == (
            "Answer the event portion of this request: Show the relevant outages "
            "Use these extracted values as required filters: asset TX-17, feeder F-3, "
            "substation Central, event OUT-9, location north region."
        )

    def test_preserves_context_added_to_user_prompt(self) -> None:
        agent = EventAgent(MagicMock())
        question = agent._build_prompt(AgentRequest(
            agent="event",
            user_prompt=(
                "Which outages affect those assets?\n\n"
                'Results from agents that already completed this request:\n'
                '{"asset": {"assets": [{"asset_id": "TX-17"}]}}'
            ),
        ))

        assert question == (
            "Answer the event portion of this request: Which outages affect those assets?\n\n"
            "Results from agents that already completed this request:\n"
            '{"asset": {"assets": [{"asset_id": "TX-17"}]}}'
        )