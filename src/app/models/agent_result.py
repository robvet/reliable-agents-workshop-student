from pydantic import BaseModel

from .trace_step import TraceStep


class AgentResult(BaseModel):
    """Every domain agent returns this — never a raw string."""
    agent: str
    data: dict = {}
    trace_step: TraceStep
    success: bool = True
