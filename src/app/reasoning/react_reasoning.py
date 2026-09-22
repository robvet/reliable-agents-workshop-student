"""ReAct reasoning: propose the next domain agent for the orchestrator to run."""
from agent_framework import Agent, ChatOptions
from agent_framework.openai import OpenAIChatClient

from ..config.config import Settings
from ..identity.azure_identity_provider import AzureIdentityProvider
from ..models.react_decision import ReActDecision
from ..models.trace_step import TraceStep
from ..utils.prompt_loader import PromptLoader


class ReActReasoning:
    """
    Implements a ReAct reasoning pattern: the model chooses one agent to run, 
    that agent runs, and the result is observed. Note that the model never runs 
    agents itself. Instead, it proposes the next agent to run, and the orchestrator 
    runs that agent and observes the result.

    Selects one domain agent at a time; the orchestrator runs and observes it.

    Deferred ideas (discussed, not implemented - captured so they aren't lost):
        
        - Keyword backstop: a free, code-only check that cross-references DOMAIN
          keywords in the user's raw prompt against which allowed agents have run,
          to catch cases where the model is confidently wrong (high confidence,
          still missed a domain). Confidence-gating alone can't catch that case -
          it only catches the model contradicting itself.
    """

    # Stop only once the model reports this much confidence the request is answered.
    STOP_CONFIDENCE = 0.8

    # If the model claims done but confidence says otherwise, ask it to explain
    # the gap and retry, this many times, before treating it as a real failure.
    MAX_CONTRADICTION_RETRIES = 2

    def __init__(self) -> None:
        # Build the model agent ONCE at startup and reuse it for every step of every
        # request. It runs on the small, cheap intent SLM - this is a quick "which one
        # agent next?" judgment, not heavy text synthesis.
        settings = Settings.get_instance()
        identity = AzureIdentityProvider.default()
        client = OpenAIChatClient(
            azure_endpoint=settings.azure_openai_endpoint,
            model=settings.intent_slm_deployment,
            credential=identity.token_provider,
        )
        # react.jinja2 tells the model its whole job: given the request and the list of
        # allowed agents, name the ONE next agent to run, or say stop. Nothing else.
        self._agent: Agent = Agent(
            client=client,
            name="react",
            instructions=PromptLoader.render("system/react.jinja2"),
            default_options={
                "reasoning": {"effort": "high", "summary": "detailed"},
                "store": False,
            },
        )

    async def reason(self, user_prompt: str, catalog: dict[str, str]) -> list[ReActDecision]:
        """Propose the next agent (or stop) for one step of the orchestrator's loop.

        The orchestrator owns the control loop, allow-list, and dispatch. This method
        only asks the model to choose, and resolves the one model quirk that is pure
        reasoning: a "done" claim (next_agent=null) whose own confidence says the
        request is not actually satisfied. It re-asks the model to name the gap up to
        MAX_CONTRADICTION_RETRIES times, then treats a still-unconfident "done" as a
        real failure.

        Returns every decision made this call, in order - a contradiction retry used to
        be discarded and invisible to the Execution Trace. The last entry is the
        decision to act on.
        """
        decisions = [await self._decide(user_prompt, catalog)]

        # The model sometimes contradicts itself: it says "done" (next_agent=null) while
        # its own confidence is below the bar - i.e. it hasn't really answered but wants
        # to stop. Don't trust that null. Re-ask it to name the missing piece and pick
        # the agent for it, up to MAX_CONTRADICTION_RETRIES times.
        while (
            decisions[-1].next_agent is None
            and decisions[-1].confidence < self.STOP_CONFIDENCE
            and len(decisions) - 1 < self.MAX_CONTRADICTION_RETRIES
        ):
            user_prompt += (
                f"\n\nYou set next_agent to null but confidence was only "
                f"{decisions[-1].confidence:.2f} (below {self.STOP_CONFIDENCE}). Name "
                f"specifically what part of the request is still unanswered, and "
                f"choose the agent needed to answer it."
            )
            decisions.append(await self._decide(user_prompt, catalog))

        # A "done" claim the model never grew confident in is a real failure, not a stop.
        final = decisions[-1]
        if final.next_agent is None and final.confidence < self.STOP_CONFIDENCE:
            raise RuntimeError(
                f"Low confidence ({final.confidence}) with no next_agent "
                f"after {len(decisions) - 1} retries"
            )

        return decisions

    def to_trace_step(self, decision: ReActDecision, is_first_decision: bool) -> TraceStep:
        # One trace entry per _decide() call - the model's next-agent choice and why.
        # The UI only renders `detail`, not `summary`, so the confidence and
        # next_agent must live in `detail` to actually appear in the trace.
        detail: dict[str, str] = {"next_agent": decision.next_agent or "stop"}
        if not is_first_decision:
            detail["confidence"] = f"{decision.confidence:.2f}"
        detail["reasoning"] = decision.reasoning
        return TraceStep(
            agent="react",
            action="decide",
            summary=f"Decision: next_agent={decision.next_agent or 'stop'} (confidence={decision.confidence:.2f})",
            detail=detail,
        )

    async def _decide(self, user_prompt: str, catalog: dict[str, str]) -> ReActDecision:
        # THE model call - one round trip. Hand the model the prompt plus the catalog of
        # ALLOWED agents, and get back a ReActDecision: which agent to run next, or stop.
        # This only PROPOSES a choice; it never runs the agent. The orchestrator runs it
        # after reason() returns.
        prompt = PromptLoader.render(
            "react_decision.jinja2",
            user_prompt=user_prompt,
            agents=catalog,
        )
        # response_format=ReActDecision makes the model return schema-shaped JSON that
        # Agent Framework parses straight into a ReActDecision - no manual JSON handling.
        response = await self._agent.run(
            prompt,
            options=ChatOptions(response_format=ReActDecision),
        )
        decision = response.value
        # Guard: if the model somehow returned something off-schema, fail loudly rather
        # than hand the orchestrator a bad decision.
        if not isinstance(decision, ReActDecision):
            raise RuntimeError("ReAct model did not return a ReActDecision")
        return decision