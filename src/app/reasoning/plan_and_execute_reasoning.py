"""Plan-and-Execute reasoning: propose, validate, then run an ExecutionPlan."""
import logging
from collections.abc import AsyncIterator

from agent_framework import Agent, ChatOptions
from agent_framework.openai import OpenAIChatClient
from opentelemetry import trace

from ..config.config import Settings
from ..identity.azure_identity_provider import AzureIdentityProvider
from ..models.agent_request import AgentRequest
from ..models.agent_result import AgentResult
from ..models.entities import Entities
from ..models.execution_plan import ExecutionPlan
from ..models.intent import Intent
from ..models.intent_result import IntentResult
from ..models.plan_step import PlanStep
from ..models.request_model import RequestModel
from ..utils.prompt_loader import PromptLoader
from ..agents.domain_agent_factory import DomainAgentFactory
from ..policy.routing_map import RoutingMap
from ..context.context_builder import ContextBuilder


class PlanAndExecuteReasoning:
    """Plan once with the model; validate and execute with deterministic code.

    The model returns an ordered list of authorized agents. It never runs the
    agents or revises the plan. Invalid plans run nothing.
    """

    MAX_STEPS = 8

    def __init__(
            self, 
            domain_agent_factory: DomainAgentFactory
        ) -> None:

        """Build a DECLARATIVE planner agent ONCE at STARTUP and resuse across the app lifetime."""

        self._factory = domain_agent_factory

        settings = Settings.get_instance()
        identity = AzureIdentityProvider.default()

        # Enables access to a deployed hosted Azure SLM
        # This model client proposes plans only; domain agents perform the work.
        client = OpenAIChatClient(
            azure_endpoint=settings.azure_openai_endpoint,
            model=settings.intent_slm_deployment,
            credential=identity.token_provider,
        )

        # Planner agent is declarative, inline agent created for the app lifetime.
        # It's not a domain agent nor registered with the DomainAgentFactory.
        # Its prompt directs the model to propose a typed plan over allowed agents.
        self._agent: Agent = Agent(
            client=client,
            name="planner",
            instructions=PromptLoader.render("system/planner.jinja2"),
            default_options={
                "reasoning": {"effort": "high", "summary": "detailed"},
                "store": False,
            },
        )
        self._tracer = trace.get_tracer(__name__)
        self._context = ContextBuilder()

    async def orchestrate_plan(
            self, 
            intent_result: IntentResult, 
            request: RequestModel,
        ) -> AsyncIterator[AgentResult | ExecutionPlan]:

        """Generate, validate, publish, and execute a new plan for this each user request."""

        with self._tracer.start_as_current_span("planner.orchestrate_plan") as span:

            # Get the agents authorized for this intent from the routing policy.
            # IMPORTANT: Acts as an allow-list that enforces deterministic control by constraining
            # which domain agents the planner model may select.
            allowed = RoutingMap.allowed_agents(intent_result.intent)
            span.set_attribute("allowed_agents", allowed)

            # UNKNOWN and ERROR intents skip domain execution. The response
            # assembler renders user-facing messages.
            if intent_result.intent in (Intent.UNKNOWN, Intent.ERROR):
                return

            # Every operational intent must authorize at least one domain agent.
            if not allowed:
                raise RuntimeError(
                    f"No agents configured for intent: {intent_result.intent}"
                )

            if intent_result.intent is Intent.DOMAIN_LOOKUP:
                agent_name = allowed[0]
                agent = self._factory.get(agent_name)
                if agent is None:
                    raise RuntimeError(f"Agent is not available: {agent_name}")
                result = await agent.handle(AgentRequest(
                    agent=agent_name,
                    entities=intent_result.entities,
                    user_prompt=request.user_prompt,
                ))
                yield result
                return

            # Ask the model to propose a plan, then validate it deterministically.
            plan = await self._build_plan(request.user_prompt, intent_result, allowed)
            steps = self._validate(plan, allowed)
            span.set_attribute("plan_valid", True)

            # Stream the validated steps to the caller. Agent execution begins in _run().
            yield ExecutionPlan(steps=steps)

            async for result in self._run(
                steps,
                intent_result.entities,
                request.user_prompt,
            ):
                yield result

    async def _build_plan(
        self,
        user_prompt: str,
        intent_result: IntentResult,
        allowed: list[str],
    ) -> ExecutionPlan:

        """
            Ask the model for a structured ExecutionPlan over the allowed agents:
            - Reads the user prompt and classified intent.
            - Receives a catalog of agents already authorized for that intent.
            - Chooses which of those agents are needed.
            - Orders the plan steps for execution.
            - Returns a structured ExecutionPlan matching the Pydantic schema
        """

        prompt = PromptLoader.render(
            "plan_generation.jinja2",
            user_prompt=user_prompt,
            intent=intent_result.intent.value,
            agents=self._factory.catalog(allowed),
        )

        
        response = await self._agent.run(
            prompt,
            options=ChatOptions(response_format=ExecutionPlan),
        )

        plan = response.value
        if not isinstance(plan, ExecutionPlan):
            raise RuntimeError("Planner model did not return an ExecutionPlan")
        return plan


    def _validate(self, plan: ExecutionPlan, allowed: list[str]) -> list[PlanStep]:
        """Validate the plan against the allow-list; return the steps in the planner's order."""
        steps = plan.steps
        if not steps or len(steps) > self.MAX_STEPS:
            raise RuntimeError("Execution plan must contain 1 to 8 steps")

        # The allow-list is the security boundary: the model may only pick agents this
        # intent authorizes.
        allowed_set = set(allowed)
        for step in steps:
            if step.agent not in allowed_set:
                raise RuntimeError(f"Agent is not allowed for this intent: {step.agent}")
        return steps

    async def _run(
        self,
        steps: list[PlanStep],
        entities: Entities,
        user_prompt: str,
    ) -> AsyncIterator[AgentResult]:
        """Execute the plan in order, feeding each step the results of the prior steps."""
        with self._tracer.start_as_current_span("planner.run") as span:
            # WORKING MEMORY: this run's results, accumulated in order. Per-request scratch
            # state - created when _run() starts, discarded when it finishes. It is NOT
            # conversation history or persistent memory.
            completed: list[AgentResult] = []

            for step in steps:

                # Resolve the app-lifetime domain agent selected by the approved plan.
                agent = self._factory.get(step.agent)
                if agent is None:
                    raise RuntimeError(f"Agent is not available: {step.agent}")

                # CONTEXT ASSEMBLY: the ContextBuilder supplements the original request
                # with every prior result so each later agent knows what already happened.
                # Later selection, summarization, and token limits stay inside that class.
                agent_request = AgentRequest(
                    agent=step.agent,
                    entities=entities,
                    user_prompt=self._context.build(user_prompt, completed),
                )

                logging.info(
                    "PlanAndExecuteReasoning: dispatching step=%s agent=%s",
                    step.id,
                    step.agent,
                )

                # Execute this plan step. The planner waits here while the selected
                # domain agent handles the validated request and returns an AgentResult.
                result = await agent.handle(agent_request)

                if result.agent != step.agent:
                    raise RuntimeError(
                        f"Step {step.id} expected agent {step.agent}, got {result.agent}"
                    )
                if not result.success:
                    raise RuntimeError(f"Agent failed: {step.agent}")

                completed.append(result)
                logging.info(
                    "PlanAndExecuteReasoning: finished step=%s agent=%s success=%s",
                    step.id,
                    step.agent,
                    result.success,
                )

                # Stream each completed step while later steps continue.
                yield result

            span.set_attribute("results_count", len(completed))
