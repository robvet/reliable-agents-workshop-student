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
    """Process one user request through the pipeline and stream progress events.

       Yields intent, reasoning, dispatch, agent-result, and final or error events.
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

    # Prevent the ReAct loop from running indefinitely.
    MAX_STEPS = 8


    def __init__(
        self,
        reasoning: ReActReasoning,
        conversation_memory: IConversationMemory,
        domain_agent_factory: DomainAgentFactory,
    ) -> None:
        """Initialize the services and dependencies used by the pipeline."""
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
        """Run the orchestration pipeline and yield progress events as they occur.

           DEBUGGING: This is the main entry point — set breakpoint here.
        """
        print(f"\n[Orchestrator] (stream) Received: {request.user_prompt}")

        with self._tracer.start_as_current_span("orchestrator.process_request_stream"):

            ##############################################################################
            # Deterministic outer pipeline: classify -> reason -> compose.
            ##############################################################################
        
            # Load prior conversation turns for intent classification.
            if request.conversation_id:
                request.history = self._conversation.load(request.conversation_id)
                logging.info(
                    "Orchestrator: loaded %d prior turn(s) for conversation=%s",
                    len(request.history), request.conversation_id,
                )

            # ########################################################################
            # Step 1: Classify the intent of the user prompt, then announce it.
            # ########################################################################
            try:
                # Call the intent classifier to classify the request
                intent_result = await self._intent_classifier.classify(request.user_prompt, request.history)
            except Exception as ex:
                logging.exception("Orchestrator.process_request_stream: classify failed")
                yield self._error_event(ex)
                return

            # Record the reasoning pattern used by this pipeline.
            intent_result.reasoning_pattern = "ReACT Reasoning Pattern"

            # Stream the classified intent to the Execution Trace display in the UI.   
            yield self._stream_events.build("intent", intent_result)

            # Short-circuit:UNKNOWN/ERROR both have no allowed agents, so we skip the ReAct loop.
            if intent_result.intent in (Intent.UNKNOWN, Intent.ERROR):
                # Call ReponseAssembler class to immediately return the appropriate final response
                # for unsupported requests or classification failures and return control.
                chat_result = await self._assembler.assemble(intent_result, [], request.user_prompt)
                yield self._stream_events.build("final", chat_result)
                return


            # ########################################################################
            # Step 2: ReAct control loop -- select agent to handle the request
            # ########################################################################            
            # Invoke ReAct loop where model will select the next agent to handle the request.
            # This orchestrator validates that choice, enforces the intent's allow-list, 
            # dispatches the agent, and observes the result. 
            # The ReAct will iterate until the response is answered or until MAX_STEPS is reached.
            # Each iteration contributes one AgentResult to `results`.
            results: list[AgentResult] = []

            try:
                # Important deterministic step: Fetch list of agents authorized for this intent.
                allowed = RoutingMap.allowed_agents(intent_result.intent)

                # Populate the authorized agent catalog presented to the reasoning model.
                catalog = self._factory.catalog(allowed)

                # Limit the ReAct loop to the configured maximum number of steps.
                for _ in range(self.MAX_STEPS):

                    # An empty results list means this is the first call to the ReAct loop for this request
                    is_first_decision = not results

                    # Build the next prompt from the request and results collected so far.
                    enriched_prompt = self._context.build(request.user_prompt, results)


                    # Ask the model to recommend the next agent or to stop.
                    # Decisions: List next_agent, confidence, reasoning
                    decisions = await self._reasoning.reason(enriched_prompt, catalog)

                    # Send every reasoning decision to the Execution Trace display in the UI.      
                    for step_decision in decisions:
                        yield self._stream_events.build(
                            "step", self._reasoning.to_trace_step(step_decision, is_first_decision)
                        )

                    # Use the final decision to stop or select the next agent.
                    decision = decisions[-1]

                    # Stop when the model recommends no next agent.
                    if decision.next_agent is None:
                        break

                    # Reject agents outside the intent's allow-list.
                    if decision.next_agent not in allowed:
                        raise RuntimeError(
                            f"Agent is not allowed for this intent: {decision.next_agent}"
                        )

                    # Get the selected agent; fail if it is not registered.
                    agent = self._factory.get(decision.next_agent)
                    if agent is None:
                        raise RuntimeError(f"Agent is not available: {decision.next_agent}")

                    # Announce the agent dispatch in the Execution Trace display in the UI.
                    yield self._stream_events.build("step", TraceStep(
                        agent=decision.next_agent,
                        action="dispatch",
                        summary=f"Calling {decision.next_agent} agent to fetch data",
                    ))

                    # Call the selected agent with the entities and enriched prompt.
                    result = await agent.handle(AgentRequest(
                        agent=decision.next_agent,
                        entities=intent_result.entities,
                        user_prompt=enriched_prompt,
                    ))

                    # Save the result for the next reasoning step and final response.
                    results.append(result)



                    # Send the agent's result summary, not its full data, to the Execution 
                    # Trace display in the UI.
                    yield self._stream_events.build("step", result.trace_step)

                    # Ignore generated NL2SQL text fields when comparing results. Their wording 
                    # can change between calls even when the returned entity data is identical.
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


            # ########################################################################
            # Step 3: Hand the collected results to the assembler, which builds the
            # ########################################################################
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

            # Send the completed response as the stream's final success event.
            yield self._stream_events.build("final", chat_result)
           

    def _error_event(self, error: Exception) -> StreamEvent:
        """
        Build the final stream event when processing fails.
        Show exception details only when verbose errors are enabled.
        """
        message = str(error) if self._show_verbose_errors else "The system encountered a technical issue."
        return StreamEvent(
            type="error",
            payload={"message": message},
        )
