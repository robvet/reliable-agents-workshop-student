"""AnswerNarratorService — writes the natural-language answer from typed agent results."""
import json
import logging

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from opentelemetry import trace

from ..config.config import Settings
from ..identity.azure_identity_provider import AzureIdentityProvider
from ..models.agent_result import AgentResult
from ..models.intent_result import IntentResult
from ..utils.prompt_loader import PromptLoader


class AnswerNarratorService:
    # *********************************************
    # *********  Architectural Insights *************
    # *********************************************
    # Pattern: Adapter over Agent Framework, mirroring LlmIntentClassifier.
    # - The SECOND (and final) live model call in the pipeline: it turns the typed
    #   agent results into an operator-facing narrative. Everything upstream stays
    #   deterministic; this is a pure render-from-structure step.
    # - Plain text output (no structured schema). Low reasoning effort keeps it fast.
    # - The caller (ResponseAssemblerService.assemble) owns graceful degrade: if
    #   synthesize() raises, it falls back to the deterministic stitch. This class
    #   does not judge.
    """Writes the final answer text from validated agent results."""

    # Keys that are diagnostic/verbose, not answer content — dropped before the model sees them.
    _NOISE_KEYS = ("sql", "question", "reasoning")
    # Cap list-valued data so a large result set can't blow up the prompt.
    _MAX_ROWS = 50

    def __init__(self) -> None:
        """Build the AF Responses-API agent bound to the intent SLM deployment (reused)."""
        settings = Settings.get_instance()
        identity = AzureIdentityProvider.default()

        client = OpenAIChatClient(
            azure_endpoint=settings.azure_openai_endpoint,
            # Inference/synthesis model (not the intent SLM); fall back to the intent
            # deployment if the inference deployment is not configured.
            model=settings.inference_lm_deployment or settings.intent_slm_deployment,
            credential=identity.token_provider,
        )

        self._agent: Agent = Agent(
            client=client,
            name="answer-narrator",
            instructions=PromptLoader.render("system/answer_narrator.jinja2"),
            default_options={
                # Fast narrative synthesis — 'medium' is the lowest effort supported
                # across models (the pro model rejects 'low'; mini accepts 'medium').
                "reasoning": {"effort": "medium"},
                "store": False,
            },
        )

        self._tracer = trace.get_tracer(__name__)

    async def synthesize(
        self,
        question: str,
        intent_result: IntentResult,
        results: list[AgentResult],
    ) -> str:
        """Render an operator-facing answer from the agent results. Raises on model failure."""
        with self._tracer.start_as_current_span("answer_narrator.synthesize") as span:
            findings = self._build_findings(results)
            prompt = PromptLoader.render(
                "narrate_answer.jinja2",
                question=question,
                intent=intent_result.intent.value,
                findings=findings,
            )
            response = await self._agent.run(prompt)
            answer = self._extract_text(response)
            span.set_attribute("answer_narrator.answer_length", len(answer))
            logging.info("AnswerNarratorService.synthesize: answer_length=%d", len(answer))
            return answer

    # --- helpers -----------------------------------------------------------

    def _build_findings(self, results: list[AgentResult]) -> str:
        """Compact, model-friendly view of each agent's result (summary + trimmed data)."""
        blocks: list[str] = []
        for result in results:
            data = self._trim_data(result.data)
            blocks.append(
                f"[{result.agent}] success={result.success}\n"
                f"  summary: {result.trace_step.summary}\n"
                f"  data: {json.dumps(data, default=str)}"
            )
        return "\n".join(blocks)

    def _trim_data(self, data: dict) -> dict:
        """Drop diagnostic keys and cap list lengths so the prompt stays small."""
        trimmed: dict = {}
        for key, value in (data or {}).items():
            if key in self._NOISE_KEYS:
                continue
            if isinstance(value, list):
                trimmed[key] = value[: self._MAX_ROWS]
            else:
                trimmed[key] = value
        return trimmed

    def _extract_text(self, response: object) -> str:
        """Extract answer text across AF response shapes (mirrors nl2sql/_extract_text)."""
        if isinstance(response, str):
            return response.strip()

        value = getattr(response, "text", None)
        if isinstance(value, str) and value:
            return value.strip()

        value = getattr(response, "content", None)
        if isinstance(value, str) and value:
            return value.strip()

        contents = getattr(response, "contents", None)
        if isinstance(contents, list):
            parts = []
            for part in contents:
                part_text = getattr(part, "text", getattr(part, "content", None))
                if isinstance(part_text, str) and part_text:
                    parts.append(part_text)
            if parts:
                return "\n".join(parts).strip()

        return str(response).strip()
