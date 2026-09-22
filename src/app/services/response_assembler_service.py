"""ResponseAssemblerService - turns the collected agent results into the final ChatResult."""
import logging

from opentelemetry import trace

from ..models.agent_result import AgentResult
from ..models.chat_result import ChatResult
from ..models.intent import Intent
from ..models.intent_result import IntentResult
from .answer_narrator_service import AnswerNarratorService


class ResponseAssemblerService:
    """Builds the final ChatResult from the intent and the agent results."""

    def __init__(self) -> None:
        """Build the narrator that writes the prose answer."""
        self._narrator = AnswerNarratorService()
        self._tracer = trace.get_tracer(__name__)

    async def assemble(
        self,
        intent: IntentResult,
        results: list[AgentResult],
        user_prompt: str,
    ) -> ChatResult:
        """Render the final answer: NL synthesis over the typed results, with a
        deterministic fallback. Classification/error paths stay deterministic."""
        with self._tracer.start_as_current_span("response_assembler.assemble") as span:
            # *********************************************
            # *********  Architectural Insights *************
            # *********************************************
            # ERROR short-circuit (checked FIRST, before the no-results path). When the
            # intent hop faulted, IntentResult.error carries the technical detail. We
            # render a soft, user-safe apology as the answer and tuck the raw detail into
            # ChatResult.artifacts["error"] - visible to operators/clients, already logged
            # upstream, but never shown as the user's answer. This is deliberately distinct
            # from the genuine-UNKNOWN fallback below: a system fault must not be dressed up
            # as a benign "I can help with asset restoration" message.
            if intent.intent is Intent.ERROR:
                span.set_attribute("error", True)
                logging.info("ResponseAssemblerService.assemble: rendering ERROR apology; detail=%s", intent.error)
                return ChatResult(
                    intent=intent.intent,
                    confidence=intent.confidence,
                    reasoning=intent.reasoning,
                    entities=intent.entities,
                    agents=[],
                    answer="Please accept our apologies as our system is currently encountering a technical issue.",
                    steps=[],
                    artifacts={"error": intent.error},
                )

            if not results:
                span.set_attribute("steps_count", 0)
                logging.info("ResponseAssemblerService.assemble: no agent results to compose")
                return ChatResult(
                    intent=intent.intent,
                    confidence=intent.confidence,
                    reasoning=intent.reasoning,
                    entities=intent.entities,
                    agents=[],
                    answer="I can only help with requests about managing or reporting on assets, outages, crews, and restoration. Please rephrase your request to focus on one of those areas.",
                    steps=[],
                )

            # Deterministic stitch — kept as the fallback if NL synthesis fails.
            deterministic = "Here's what I found:\n" + "\n".join(
                f"{result.agent}: {result.trace_step.summary}" for result in results
            )
            # The SECOND (final) live model call: render the typed results into an
            # operator-facing narrative. Degrade to the deterministic stitch on failure.
            try:
                answer = await self._narrator.synthesize(user_prompt, intent, results)
            except Exception:
                logging.exception(
                    "ResponseAssemblerService.assemble: NL synthesis failed; using deterministic answer"
                )
                answer = deterministic
            asset_result = next((result for result in results if result.agent == "asset"), None)
            assets = asset_result.data.get("assets") if asset_result is not None else None
            artifacts = {"assets": assets} if isinstance(assets, list) else {}
            chat_result = ChatResult(
                intent=intent.intent,
                confidence=intent.confidence,
                reasoning=intent.reasoning,
                entities=intent.entities,
                agents=[result.agent for result in results],
                answer=answer,
                steps=[result.trace_step for result in results],
                artifacts=artifacts,
            )

            span.set_attribute("steps_count", len(chat_result.steps))
            logging.info(
                "ResponseAssemblerService.assemble: steps_count=%d answer_length=%d",
                len(chat_result.steps),
                len(chat_result.answer),
            )
            return chat_result

