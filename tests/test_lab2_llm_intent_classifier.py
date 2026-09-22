from unittest.mock import AsyncMock, MagicMock

import pytest

from app.intent.llm_intent_classifier import LlmIntentClassifier
from app.models.intent import Intent
from app.models.intent_result import IntentResult


class TestLab2LlmIntentClassifier:
    """Verify the four classification outcomes implemented during Lab 2.

    Each test replaces the real model call with a controlled response so the
    classifier's deterministic behavior can be tested without Azure OpenAI.
    """

    @staticmethod
    def _build_classifier(run: AsyncMock) -> LlmIntentClassifier:
        """Create a classifier with mocked model and telemetry dependencies."""
        classifier = LlmIntentClassifier.__new__(LlmIntentClassifier)
        classifier._agent = MagicMock()
        classifier._agent.run = run
        classifier._tracer = MagicMock()
        return classifier

    @staticmethod
    def _print_call_details(run: AsyncMock, result: IntentResult) -> None:
        """Show what crossed the mocked model boundary during the test."""
        call = run.await_args
        response_format = call.kwargs["options"]["response_format"]
        response_format_name = getattr(response_format, "__name__", str(response_format))
        if run.side_effect:
            mocked_outcome = f"raises {type(run.side_effect).__name__}: {run.side_effect}"
        else:
            mocked_outcome = repr(run.return_value.value)

        print("\n--- Mock model call (no Azure OpenAI request) ---")
        print(f"Rendered prompt:\n{call.args[0]}")
        print(f"Response format: {response_format_name}")
        print(f"Mocked model outcome: {mocked_outcome}")
        print(f"Final classifier result:\n{result.model_dump_json(indent=2)}")
        print("--- End mock model call ---\n")

    @pytest.mark.asyncio
    async def test_lab2_valid_intent_result_passes_through_unchanged(self) -> None:
        """A valid structured model result is returned without modification."""
        # Arrange: make the model return a known, valid classification.
        expected = IntentResult(
            intent=Intent.EVENT_RESPONSE,
            confidence=0.95,
            reasoning="The request reports an outage.",
        )
        run = AsyncMock(return_value=MagicMock(value=expected, messages=[]))
        classifier = self._build_classifier(run)

        # Act: classify a supported request.
        result = await classifier.classify("Report an outage at Central substation")
        self._print_call_details(run, result)

        # Assert: the classifier returns the exact object supplied by the model.
        assert result is expected
        run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lab2_valid_unknown_remains_unknown(self) -> None:
        """A valid UNKNOWN result stays distinct from a technical ERROR."""
        # Arrange: make the model return a valid unclassifiable result.
        expected = IntentResult(
            intent=Intent.UNKNOWN,
            confidence=0.2,
            reasoning="The request is outside the supported domain.",
        )
        run = AsyncMock(return_value=MagicMock(value=expected, messages=[]))
        classifier = self._build_classifier(run)

        # Act: classify a request outside the application's supported domain.
        result = await classifier.classify("Write a poem about the ocean")
        self._print_call_details(run, result)

        # Assert: UNKNOWN remains a valid result and has no technical error.
        assert result is expected
        assert result.intent is Intent.UNKNOWN
        assert result.error is None

    @pytest.mark.asyncio
    async def test_lab2_model_exception_returns_error_with_detail(self) -> None:
        """A failed model call becomes ERROR and preserves diagnostic detail."""
        # Arrange: make the model call raise a controlled technical failure.
        run = AsyncMock(side_effect=RuntimeError("simulated model failure"))
        classifier = self._build_classifier(run)

        # Act: classify a supported request while the model call is failing.
        result = await classifier.classify("Show active outages")
        self._print_call_details(run, result)

        # Assert: deterministic code reports ERROR with the exception message.
        assert result.intent is Intent.ERROR
        assert result.error == "simulated model failure"

    @pytest.mark.asyncio
    async def test_lab2_malformed_response_returns_error_with_detail(self) -> None:
        """A response without IntentResult becomes a diagnostic ERROR result."""
        # Arrange: make the model return a dictionary instead of IntentResult.
        run = AsyncMock(
            return_value=MagicMock(value={"intent": "EVENT_RESPONSE"})
        )
        classifier = self._build_classifier(run)

        # Act: classify a request that receives malformed structured output.
        result = await classifier.classify("Show active outages")
        self._print_call_details(run, result)

        # Assert: deterministic validation rejects the malformed value as ERROR.
        assert result.intent is Intent.ERROR
        assert result.error == "classifier returned no structured result"