"""LlmIntentClassifier — intent recognition via Agent Framework + Azure OpenAI Responses API."""
import logging

from agent_framework import Agent, ChatOptions
from agent_framework.openai import OpenAIChatClient
from opentelemetry import trace

from ..config.config import Settings
from ..identity.azure_identity_provider import AzureIdentityProvider

# import intent models
from ..models.intent import Intent
from ..models.intent_result import IntentResult
from ..utils.prompt_loader import PromptLoader


class LlmIntentClassifier:
    """Classifies the user's prompt into a validated IntentResult using the intent SLM.

    Input is unstructured user text; output is a validated, structured IntentResult class. 
    Note that from this point forward, all data passed through the pipeline is structured and typed, never free text.
    Structured Inputs/Outputs increase reliability and make downstream processing more predictable.
    
    Important: Failure handling: a failed or malformed model call returns Intent.ERROR
    with a technical detail, never UNKNOWN. 
    
    UNKNOWN means "unclassifiable request"; 
    ERROR means "the system faulted" 
    """

    def __init__(self) -> None:
        """Build a core AgentFramework stateless agent that wraps calls to the intent small language model deployment."""
        # Built once and reused for every request
        # AAD tokens across calls, and classify() is stateless over this shared agent.
        settings = Settings.get_instance()
        identity = AzureIdentityProvider.default()

        # Instantiates Agent Framework client.
        client = OpenAIChatClient(
            azure_endpoint=settings.azure_openai_endpoint,
            model=settings.intent_slm_deployment,
            credential=identity.token_provider,
        )

        # Reasoning models reject temperature, so it's intentionally omitted.
        # store=False keeps responses stateless on the service side.
        self._agent: Agent = Agent(
            client=client,
            name="intent-classifier",
            instructions=PromptLoader.render("system/intent_classifier_persona.jinja2"),
            default_options={
                "reasoning": {"effort": "high", "summary": "detailed"},
                "store": False,
            },
        )

        self._tracer = trace.get_tracer(__name__)


    async def classify(
            self, 
            user_prompt: str,
            history: list[dict] | None = None,
        ) -> IntentResult:
        """Call the SLM with structured output; return a validated IntentResult."""
        with self._tracer.start_as_current_span("intent.classify") as span:

            # Step 1: Render the per-call task prompt (current message + prior turns).
            prompt = PromptLoader.render("intent_classifier_task.jinja2", user_prompt=user_prompt, history=history or [])

            # Step 2: Call the model, requesting structured output (response_format=IntentResult).
            try:
                response = await self._agent.run(
                    prompt,
                    options=ChatOptions(response_format=IntentResult),
                )
            except Exception as ex:
                # Step 2a (RELIABILITY): the call itself failed -> Intent.ERROR + detail,
                # never UNKNOWN (see class docstring).
                logging.exception("LlmIntentClassifier.classify: model call failed")
                span.set_attribute("intent", Intent.ERROR.value)
                span.set_attribute("success", False)
                span.record_exception(ex)
                return IntentResult(intent=Intent.ERROR, error=str(ex) or type(ex).__name__)

            # Step 3: Pull the structured result off the response.
            result = response.value

            if not isinstance(result, IntentResult):
                # Step 3a (RELIABILITY): call succeeded but returned no valid structure -
                # still a system fault, not a user-side UNKNOWN.
                logging.warning("LlmIntentClassifier.classify: no structured IntentResult returned")
                span.set_attribute("intent", Intent.ERROR.value)
                span.set_attribute("success", False)
                return IntentResult(
                    intent=Intent.ERROR,
                    error="classifier returned no structured result",
                )

            # Step 4: Log the classification (span attributes + reasoning summary).
            summary = self._extract_reasoning_summary(response)

            # UNKNOWN counts as success here - it's a valid result, not a failure.
            entities_set = {k: v for k, v in result.entities.model_dump().items() if v is not None}
            span.set_attribute("intent", result.intent.value)
            span.set_attribute("confidence", result.confidence)
            span.set_attribute("success", result.intent != Intent.UNKNOWN)
            span.set_attribute("entities", str(entities_set))

            if summary:
                span.set_attribute("reasoning_summary", summary)
            logging.info(
                "LlmIntentClassifier.classify: intent=%s confidence=%.2f continues_previous=%s entities=%s",
                result.intent.value,
                result.confidence,
                result.continues_previous,
                entities_set,
            )

            # Step 5: Return the validated result.
            return result

    def _extract_reasoning_summary(self, response: object) -> str:
        """Pull the model's reasoning-summary text out of the response, for logging only.

        This is a paraphrase of the model's hidden chain-of-thought, not the raw
        reasoning tokens themselves - the API never exposes those.
        """
        parts: list[str] = []
        for message in getattr(response, "messages", None) or []:
            for content in getattr(message, "contents", None) or []:
                if getattr(content, "type", None) == "text_reasoning":
                    text = getattr(content, "text", "") or ""
                    if text:
                        parts.append(text)
        return "\n".join(parts)
