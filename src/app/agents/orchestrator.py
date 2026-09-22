"""Orchestrator: deterministic Phase 0 pipeline - classify -> plan -> dispatch -> compose."""
import logging
from collections.abc import AsyncIterator

from opentelemetry import trace

# double dots mean "go up an extra directory in the folder structure" - this is a relative import
from ..models.agent_request import AgentRequest
from ..models.agent_result import AgentResult
from ..models.intent import Intent
from ..models.intent_result import IntentResult
from ..models.stream_event import StreamEvent
from ..models.trace_step import TraceStep
from ..intent.llm_intent_classifier import LlmIntentClassifier
from ..services.response_assembler_service import ResponseAssemblerService
from ..services.stream_event_service import StreamEventService
from ..reasoning.react_reasoning import ReActReasoning
from ..policy.routing_map import RoutingMap
from ..context.context_builder import ContextBuilder
from .domain_agent_factory import DomainAgentFactory
from ..models.request_model import RequestModel
from ..context.i_conversation_memory import IConversationMemory
from ..config.config import Settings


class Orchestrator:
    """
    Single responsibility: orchestrate the typed pipeline for one user message.

    Architecture role:
    - Similar to an application service in C#/Java.
    - Every hop from IntentResult onward is a validated Pydantic object -
      no free text passes between the model hop and the final rendered answer.
    - Control flow is deterministic: the model proposes (intent only, this phase);
      this class validates and routes.
    """

    # *********************************************
    # *********  Architectural Insights *************
    # *********************************************
    # Pattern: Orchestrator owns the deterministic control loop.
    # - Deterministic outer pipeline: classify -> reason -> compose.
    # - Intent classification is delegated to LlmIntentClassifier.
    # - The ReAct loop lives HERE: the injected reasoning only proposes the next
    #   agent; this class validates the choice, enforces the allow-list, dispatches
    #   the agent, and observes the result.

    # Maximum number of ReAct steps before giving up. The model must answer the
    # request within this many agent dispatches.
    MAX_STEPS = 8

    def __init__(
        self,
        reasoning: ReActReasoning,
        conversation_memory: IConversationMemory,
        domain_agent_factory: DomainAgentFactory,
    ) -> None:
        """Create the intent classifier and receive the reasoning + conversation memory store.

        conversation_memory = session-lived, distilled (feeds the classifier).
        """
        self._intent_classifier = LlmIntentClassifier()
        self._assembler = ResponseAssemblerService()
        self._stream_events = StreamEventService()
        self._reasoning = reasoning
        self._factory = domain_agent_factory
        self._context = ContextBuilder()
        self._conversation = conversation_memory
        self._show_verbose_errors = Settings.get_instance().show_verbose_errors
        self._tracer = trace.get_tracer(__name__)


    async def process_request_stream(
        self, 
        request: RequestModel
    ) -> AsyncIterator[StreamEvent]:
        """Process a user request end-to-end, yielding events live as they happen.

        THE production path. Every request the UI makes lands here.

        Emits: one 'intent' event, one 'step' event per agent as it finishes, then a
        single 'final' event carrying the composed ChatResult (or an 'error' event).

        Args:
            request: Typed inbound request (user prompt + forward-compatible context).
        Yields:
            StreamEvent envelopes in pipeline order.

        DEBUGGING: This is the main entry point — set breakpoint here.
        """
        print(f"\n[Orchestrator] (stream) Received: {request.user_prompt}")

        with self._tracer.start_as_current_span("orchestrator.process_request_stream"):

            ##############################################################################
            # Deterministic outer pipeline: classify -> reason -> compose.
            ##############################################################################

            # Load prior turns for this conversation onto request.history (empty when there
            # is no id or no history). Intent classifier consumes this in a later slice.
            if request.conversation_id:
                request.history = self._conversation.load(request.conversation_id)
                logging.info(
                    "Orchestrator: loaded %d prior turn(s) for conversation=%s",
                    len(request.history), request.conversation_id,
                )

            # Step 1: Classify the intent of the user prompt, then announce it.
            try:
                # This is call to the intent classifier, which involves a classification model call.
                intent_result = await self._intent_classifier.classify(request.user_prompt, request.history)
            except Exception as ex:
                logging.exception("Orchestrator.process_request_stream: classify failed")
                yield self._error_event(ex)
                return

            # Stamp which reasoning pattern this orchestrator is configured with.
            intent_result.reasoning_pattern = "ReACT Reasoning Pattern"

            # Send the intent event message to the UI Execution Trace.
            yield self._stream_events.build("intent", intent_result)

            # UNKNOWN/ERROR short-circuit: both have an empty agent allow-list
            # (RoutingMap), so there is nothing for the ReAct loop to reason about -
            # skip it entirely and let the assembler render the right message
            # (technical apology for ERROR, out-of-scope decline for UNKNOWN).
            if intent_result.intent in (Intent.UNKNOWN, Intent.ERROR):
                chat_result = await self._assembler.assemble(intent_result, [], request.user_prompt)
                yield self._stream_events.build("final", chat_result)
                return

            # Step 2: ReAct control loop. The reasoning component proposes one agent
            # at a time (the model proposes); this orchestrator validates that choice,
            # enforces the intent's allow-list, dispatches the agent, and observes the
            # result - looping until the model reports done or MAX_STEPS is reached.
            # Each finished agent contributes one AgentResult to `results`.
            results: list[AgentResult] = []

            try:
                # Same allow-list the planner enforced - keeps ReAct from reaching
                # agents this intent doesn't authorize (e.g. direct_query under
                # CROSS_DOMAIN). The catalog the model chooses from is built from it.
                allowed = RoutingMap.allowed_agents(intent_result.intent)
                catalog = self._factory.catalog(allowed)

                for _ in range(self.MAX_STEPS):
                    # Confidence is meaningless before any agent has answered - only
                    # show it once at least one AgentResult has come back.
                    is_first_decision = not results
                    enriched_prompt = self._context.build(request.user_prompt, results)

                    # The model proposes the next agent (or stop); deterministic code
                    # below validates and runs it. reason() returns every attempt it made
                    # this step, including contradiction retries - trace all of them, not
                    # just the last one, so a retry is visible instead of vanishing.
                    decisions = await self._reasoning.reason(enriched_prompt, catalog)
                    for step_decision in decisions:
                        yield self._stream_events.build(
                            "step", self._reasoning.to_trace_step(step_decision, is_first_decision)
                        )
                    decision = decisions[-1]

                    if decision.next_agent is None:
                        break

                    if decision.next_agent not in allowed:
                        raise RuntimeError(
                            f"Agent is not allowed for this intent: {decision.next_agent}"
                        )

                    # Creates an instance of the selected agent.
                    agent = self._factory.get(decision.next_agent)
                    if agent is None:
                        raise RuntimeError(f"Agent is not available: {decision.next_agent}")

                    yield self._stream_events.build("step", TraceStep(
                        agent=decision.next_agent,
                        action="dispatch",
                        summary=f"Calling {decision.next_agent} agent to fetch data",
                    ))

                    # Here is the invocation call to the selected agent.
                    # It's called with the enriched prompt and the entities the intent classifier extracted.
                    result = await agent.handle(AgentRequest(
                        agent=decision.next_agent,
                        entities=intent_result.entities,
                        user_prompt=enriched_prompt,
                    ))
                    results.append(result)

                    # trace_step is the short, display-safe summary of what the agent
                    # did - not the agent's full data payload. Send it now so progress
                    # appears live in the browser.
                    yield self._stream_events.build("step", result.trace_step)

                    # No-progress guard: if this agent already returned this exact data
                    # earlier in the same run, calling it again will not produce anything
                    # new. Stop here instead of burning the rest of MAX_STEPS re-asking
                    # the same question and getting the same answer.
                    # Compare only the actual entity payload, not "sql"/"question"/
                    # "reasoning" - those are free-text NL2SQL output that differs on
                    # almost every call (the question field alone grows every step),
                    # which made this guard never fire.
                    volatile_keys = ("sql", "question", "reasoning")
                    comparable = {k: v for k, v in result.data.items() if k not in volatile_keys}
                    if any(
                        r.agent == result.agent
                        and {k: v for k, v in r.data.items() if k not in volatile_keys} == comparable
                        for r in results[:-1]
                    ):
                        break
            except Exception as ex:
                # An agent blew up. We already sent HTTP 200, so we can't return a 500 -
                # we tell the client in the stream and stop.
                logging.exception("Orchestrator.process_request_stream: agents failed")
                yield self._error_event(ex)
                return

            # Step 3: Hand the collected results to the assembler, which builds the
            # final ChatResult, and send it as the last event.
            try:
                chat_result = await self._assembler.assemble(
                    intent_result, results, request.user_prompt
                )
            except Exception as ex:
                logging.exception("Orchestrator.process_request_stream: compose failed")
                yield self._error_event(ex)
                return

            # Persist this completed turn so later turns can reference it (success path only).
            if request.conversation_id:
                self._conversation.append(request.conversation_id, {
                    "turn": len(request.history) + 1,
                    "prompt": request.user_prompt,
                    "answer": chat_result.answer,
                    "intent": chat_result.intent.value,
                    "entities": chat_result.entities.model_dump(),
                })
                logging.info(
                    "Orchestrator: appended turn %d for conversation=%s",
                    len(request.history) + 1, request.conversation_id,
                )

            # Send the final event as the terminal success message for this stream.
            yield self._stream_events.build("final", chat_result)

            # *********************************************
            # *********  Architectural Insights *************
            # *********************************************
            # THE STATUS CODE CAN'T TELL YOU IF THIS WORKED. We send HTTP 200 before any
            # of the work above runs, so by the time something breaks the status is
            # already gone. (A normal request/response can still turn a late exception
            # into a 500. We can't.)
            #
            # So the answer is in the messages, not the header. Every path out of this
            # method sends a last message - 'final' if it worked, 'error' if it didn't -
            # and the client has to read them to find out which. Checking for 200 tells
            # it nothing.
            #
            # If the stream ends without either one, the connection dropped. That's a
            # different problem from the pipeline failing, and worth telling apart.


    def _error_event(self, error: Exception) -> StreamEvent:
        """The last message we send when something breaks.

        We can't just let the exception escape. The 200 has already gone out, so an
        escaping exception just cuts the connection mid-stream - and the client can't
        tell that apart from the network dying. Sending an 'error' message says so
        plainly.

        The message is deliberately vague unless local verbose errors are enabled.
        The full exception is always retained in the server logs.
        """
        message = str(error) if self._show_verbose_errors else "The system encountered a technical issue."
        return StreamEvent(
            type="error",
            payload={"message": message},
        )


