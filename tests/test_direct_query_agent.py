from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.direct_query_agent import DirectQueryAgent
from app.models.agent_request import AgentRequest


class TestDirectQueryAgent:
    @pytest.mark.asyncio
    async def test_sends_exact_user_prompt_once(self) -> None:
        question = "How many outages are open in the south region?"
        mcp_client = MagicMock()
        mcp_client.query = AsyncMock(return_value={
            "rows": [{"count": 4}],
            "sql": "SELECT 4",
            "reasoning": "Counted open outages.",
        })

        result = await DirectQueryAgent(mcp_client).handle(AgentRequest(
            agent="direct_query",
            user_prompt=question,
        ))

        mcp_client.query.assert_awaited_once_with(question)
        assert result.agent == "direct_query"
        assert result.data["rows"] == [{"count": 4}]
        assert result.data["question"] == question
