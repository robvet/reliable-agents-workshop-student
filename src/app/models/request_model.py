from pydantic import BaseModel


class RequestModel(BaseModel):
    """Typed inbound request for the orchestration pipeline.

    Only user_prompt is populated today; system_prompt, history, and context are
    forward-compatible slots for once planning/ReAct need the system prompt, prior
    turns, or extra request context - so the entry point does not have to change again.
    """
    user_prompt: str
    conversation_id: str | None = None
    system_prompt: str | None = None
    history: list[dict] = []
    context: dict = {}
