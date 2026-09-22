from typing import Optional

from pydantic import BaseModel


class ModelResponse(BaseModel):
    """
    Response from a single model. Retained as the return type of IAgent.run_turn()
    used by the reference agents (GPT / Gemini / Anthropic).
    """
    text: str
    status: str  # "complete" or "error"
    error_message: Optional[str] = None
