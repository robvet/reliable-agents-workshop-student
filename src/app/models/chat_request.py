from pydantic import BaseModel


class ChatRequest(BaseModel):
    """External HTTP request body for POST /chat/stream."""
    message: str
    conversation_id: str | None = None
