import json

from app.context.context_builder import ContextBuilder
from app.models.agent_result import AgentResult
from app.models.trace_step import TraceStep


class TestContextBuilder:
    def test_appends_prior_business_results_to_original_prompt(self) -> None:
        completed = [
            AgentResult(
                agent="asset",
                data={
                    "assets": [{"asset_id": "TX-17"}],
                    "count": 1,
                    "question": "old enriched prompt",
                    "sql": "SELECT asset_id",
                    "reasoning": "Found the asset.",
                },
                trace_step=TraceStep(
                    agent="asset",
                    action="resolve_asset",
                    summary="resolved asset",
                ),
            ),
            AgentResult(
                agent="event",
                data={"events": [{"outage_id": "OUT-9"}], "count": 1},
                trace_step=TraceStep(
                    agent="event",
                    action="lookup_events",
                    summary="found outage",
                ),
            ),
        ]

        prompt = ContextBuilder().build("Which crews are assigned?", completed)
        context = json.loads(prompt.split("\n", 3)[-1])

        assert prompt.startswith("Which crews are assigned?\n\n")
        assert context == [
            {
                "agent": "asset",
                "data": {"assets": [{"asset_id": "TX-17"}], "count": 1},
            },
            {
                "agent": "event",
                "data": {"events": [{"outage_id": "OUT-9"}], "count": 1},
            },
        ]
        assert "old enriched prompt" not in prompt