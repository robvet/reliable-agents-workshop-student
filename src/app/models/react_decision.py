from pydantic import BaseModel, Field


class ReActDecision(BaseModel):
    next_agent: str | None
    # 0.0-1.0: does existing evidence already satisfy the user's original request?
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str