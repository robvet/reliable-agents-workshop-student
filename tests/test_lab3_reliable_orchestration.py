from unittest.mock import AsyncMock, MagicMock

import pytest
from opentelemetry import trace

from app.agents.orchestrator import Orchestrator
from app.context.context_builder import ContextBuilder
from app.models.agent_result import AgentResult
from app.models.intent import Intent
from app.models.intent_result import IntentResult
from app.models.react_decision import ReActDecision
from app.models.request_model import RequestModel
from app.models.trace_step import TraceStep
from app.services.stream_event_service import StreamEventService


class TestLab3ReliableOrchestration:
    def _orchestrator(self, reason: AsyncMock, factory: MagicMock) -> Orchestrator:
        orchestrator = Orchestrator.__new__(Orchestrator)
        reasoning = MagicMock()
        reasoning.reason = reason
        reasoning.to_trace_step = MagicMock(return_value=TraceStep(
            agent="react", action="decide", summary="decision",
        ))
        chat_result = MagicMock()
        chat_result.model_dump.return_value = {}
        orchestrator._intent_classifier = MagicMock(classify=AsyncMock(
            return_value=IntentResult(intent=Intent.EVENT_RESPONSE),
        ))
        orchestrator._assembler = MagicMock(assemble=AsyncMock(return_value=chat_result))
        orchestrator._stream_events = StreamEventService()
        orchestrator._reasoning = reasoning
        orchestrator._factory = factory
        orchestrator._context = ContextBuilder()
        orchestrator._conversation = MagicMock()
        orchestrator._show_verbose_errors = True
        orchestrator._tracer = trace.get_tracer(__name__)
        return orchestrator

    async def _run(self, orchestrator: Orchestrator, prompt: str) -> list[tuple[str, dict]]:
        return [
            (event.type, event.payload)
            async for event in orchestrator.process_request_stream(
                RequestModel(user_prompt=prompt)
            )
        ]

    @pytest.mark.asyncio
    async def test_selects_and_executes_one_agent_then_stops(self) -> None:
        asset_result = AgentResult(
            agent="asset",
            data={"assets": []},
            trace_step=TraceStep(agent="asset", action="resolve_asset", summary="0 found"),
        )
        asset_agent = MagicMock(handle=AsyncMock(return_value=asset_result))
        factory = MagicMock()
        factory.get.return_value = asset_agent
        factory.catalog.return_value = {"asset": "Resolves assets"}
        reason = AsyncMock(side_effect=[
            [ReActDecision(next_agent="asset", confidence=0.5, reasoning="Need asset data.")],
            [ReActDecision(next_agent=None, confidence=0.9, reasoning="The request is complete.")],
        ])

        events = await self._run(self._orchestrator(reason, factory), "Respond to the outage")

        factory.get.assert_called_once_with("asset")
        asset_agent.handle.assert_awaited_once()
        sent_request = asset_agent.handle.await_args.args[0]
        assert sent_request.agent == "asset"
        assert sent_request.user_prompt == "Respond to the outage"
        assert [event_type for event_type, _ in events][-1] == "final"

    @pytest.mark.asyncio
    async def test_stops_without_dispatching(self) -> None:
        factory = MagicMock()
        factory.catalog.return_value = {"asset": "Resolves assets"}
        reason = AsyncMock(return_value=[ReActDecision(
            next_agent=None, confidence=0.9, reasoning="The request is complete.",
        )])

        events = await self._run(self._orchestrator(reason, factory), "Respond to the outage")

        factory.get.assert_not_called()
        assert [event_type for event_type, _ in events][-1] == "final"

    @pytest.mark.asyncio
    async def test_rejects_agent_outside_the_allow_list(self) -> None:
        factory = MagicMock()
        factory.catalog.return_value = {"asset": "Resolves assets"}
        reason = AsyncMock(return_value=[ReActDecision(
            next_agent="customer", confidence=0.9, reasoning="Use an unauthorized agent.",
        )])

        events = await self._run(self._orchestrator(reason, factory), "Respond to the outage")

        factory.get.assert_not_called()
        error = next(payload for event_type, payload in events if event_type == "error")
        assert "not allowed" in error["message"]