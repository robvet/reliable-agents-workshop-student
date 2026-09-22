import pytest
from pydantic import ValidationError

from app.models.react_decision import ReActDecision


class TestReActDecision:
    def test_accepts_agent_selection(self) -> None:
        decision = ReActDecision(next_agent="asset", confidence=0.5, reasoning="Asset data is required.")

        assert decision.next_agent == "asset"
        assert decision.reasoning == "Asset data is required."

    def test_accepts_stop_decision(self) -> None:
        decision = ReActDecision(next_agent=None, confidence=0.9, reasoning="The request is complete.")

        assert decision.next_agent is None

    def test_requires_reasoning(self) -> None:
        with pytest.raises(ValidationError):
            ReActDecision.model_validate({"next_agent": "asset"})