"""Lab 2 exercise copy of LlmIntentClassifier.

Fill in the five steps inside classify(). Each begins with a numbered comment that
is already here; add the code beneath it. Everything else is provided, including
the constructor and _extract_reasoning_summary().

Run ./start --lab2 to use this file, and ./test-lab2 to check your work.
The complete implementation is in llm_intent_classifier.py if you need to compare.
"""

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


            # Step 2: Call the model, requesting structured output (response_format=IntentResult).

                # Step 2a (RELIABILITY): the call itself failed -> Intent.ERROR + detail,
                # never UNKNOWN (see class docstring).


            # Step 3: Pull the structured result off the response.

                # Step 3a (RELIABILITY): call succeeded but returned no valid structure -
                # still a system fault, not a user-side UNKNOWN.


            # Step 4: Log the classification (span attributes + reasoning summary).


            # Step 5: Return the validated result.
            raise NotImplementedError(
                "Lab 2: implement the classification workflow above."
            )

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
