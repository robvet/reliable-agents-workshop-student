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
from app.reasoning.react_reasoning import ReActReasoning
from app.services.stream_event_service import StreamEventService


class TestReActReason:
    """ReActReasoning is now a pure decision helper: it proposes the next agent and
    resolves the model's done/confidence contradiction, but owns no control loop."""

    def _reasoning(self, decide: AsyncMock) -> ReActReasoning:
        reasoning = ReActReasoning.__new__(ReActReasoning)
        reasoning._decide = decide
        return reasoning

    @pytest.mark.asyncio
    async def test_returns_the_models_decision(self) -> None:
        chosen = ReActDecision(next_agent="asset", confidence=0.5, reasoning="Need asset data.")
        reasoning = self._reasoning(AsyncMock(return_value=chosen))

        decisions = await reasoning.reason("Respond to the outage", {"asset": "Resolves assets"})

        assert decisions == [chosen]
        reasoning._decide.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retries_the_done_contradiction_then_returns(self) -> None:
        # Model first claims done at low confidence, then names the real next agent.
        first = ReActDecision(next_agent=None, confidence=0.2, reasoning="Looks done.")
        second = ReActDecision(next_agent="asset", confidence=0.5, reasoning="Actually need asset data.")
        reasoning = self._reasoning(AsyncMock(side_effect=[first, second]))

        decisions = await reasoning.reason("Respond to the outage", {"asset": "Resolves assets"})

        assert decisions == [first, second]
        assert reasoning._decide.await_count == 2

    @pytest.mark.asyncio
    async def test_raises_when_done_stays_unconfident(self) -> None:
        reasoning = self._reasoning(AsyncMock(return_value=ReActDecision(
            next_agent=None, confidence=0.2, reasoning="Still looks done.",
        )))

        with pytest.raises(RuntimeError, match="Low confidence"):
            await reasoning.reason("Respond to the outage", {"asset": "Resolves assets"})

        # One initial decision + MAX_CONTRADICTION_RETRIES re-asks.
        assert reasoning._decide.await_count == 1 + ReActReasoning.MAX_CONTRADICTION_RETRIES


class TestReActTraceStep:
    def test_hides_confidence_on_the_first_decision(self) -> None:
        reasoning = ReActReasoning.__new__(ReActReasoning)
        decision = ReActDecision(next_agent="asset", confidence=0.42, reasoning="why")

        step = reasoning.to_trace_step(decision, is_first_decision=True)

        assert "confidence" not in step.detail
        assert step.detail["next_agent"] == "asset"
        assert step.detail["reasoning"] == "why"

    def test_shows_confidence_after_the_first_decision(self) -> None:
        reasoning = ReActReasoning.__new__(ReActReasoning)
        decision = ReActDecision(next_agent="asset", confidence=0.42, reasoning="why")

        step = reasoning.to_trace_step(decision, is_first_decision=False)

        assert step.detail["confidence"] == "0.42"


class TestOrchestratorReActLoop:
    """The control loop the reasoning class used to own now lives in Orchestrator:
    build catalog from the allow-list, ask reason() for a choice, validate it,
    dispatch the agent, observe, and stop when the model reports done."""

    def _orchestrator(
        self, reason: AsyncMock, factory: MagicMock, intent: Intent = Intent.EVENT_RESPONSE,
    ) -> Orchestrator:
        orchestrator = Orchestrator.__new__(Orchestrator)
        reasoning = MagicMock()
        reasoning.reason = reason
        reasoning.to_trace_step = MagicMock(return_value=TraceStep(
            agent="react", action="decide", summary="decision",
        ))
        chat_result = MagicMock()
        chat_result.model_dump.return_value = {}
        orchestrator._intent_classifier = MagicMock(classify=AsyncMock(
            return_value=IntentResult(intent=intent),
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
        assert [t for t, _ in events][-1] == "final"

    @pytest.mark.asyncio
    async def test_stops_without_dispatching(self) -> None:
        factory = MagicMock()
        factory.catalog.return_value = {"asset": "Resolves assets"}
        reason = AsyncMock(return_value=[ReActDecision(
            next_agent=None, confidence=0.9, reasoning="The request is complete.",
        )])

        events = await self._run(self._orchestrator(reason, factory), "Respond to the outage")

        factory.get.assert_not_called()
        assert [t for t, _ in events][-1] == "final"

    @pytest.mark.asyncio
    async def test_rejects_agent_outside_the_allow_list(self) -> None:
        factory = MagicMock()
        factory.catalog.return_value = {"asset": "Resolves assets"}
        # "customer" is not allowed under EVENT_RESPONSE (asset/event/crew only).
        reason = AsyncMock(return_value=[ReActDecision(
            next_agent="customer", confidence=0.9, reasoning="Use an unauthorized agent.",
        )])

        events = await self._run(self._orchestrator(reason, factory), "Respond to the outage")

        factory.get.assert_not_called()
        error = next(payload for t, payload in events if t == "error")
        assert "not allowed" in error["message"]

    @pytest.mark.asyncio
    async def test_unknown_intent_bypasses_the_react_loop(self) -> None:
        factory = MagicMock()
        reason = AsyncMock()

        events = await self._run(
            self._orchestrator(reason, factory, intent=Intent.UNKNOWN),
            "Where is Cleveland?",
        )

        reason.assert_not_awaited()
        factory.catalog.assert_not_called()
        factory.get.assert_not_called()
        assert [t for t, _ in events][-1] == "final"

    @pytest.mark.asyncio
    async def test_error_intent_bypasses_the_react_loop(self) -> None:
        factory = MagicMock()
        reason = AsyncMock()

        events = await self._run(
            self._orchestrator(reason, factory, intent=Intent.ERROR),
            "Respond to the outage",
        )

        reason.assert_not_awaited()
        factory.catalog.assert_not_called()
        factory.get.assert_not_called()
        assert [t for t, _ in events][-1] == "final"
