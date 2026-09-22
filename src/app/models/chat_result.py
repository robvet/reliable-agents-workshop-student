from pydantic import BaseModel

from .entities import Entities
from .intent import Intent
from .trace_step import TraceStep


class ChatResult(BaseModel):
    """Final composed result. Surfaces the full classification (intent, confidence,
    reasoning, entities, agents chosen) alongside the rendered answer and trace steps,
    so no routing decision is a black box - even an UNKNOWN fallback is explained."""
    intent: Intent = Intent.UNKNOWN
    confidence: float = 0.0
    reasoning: str = ""
    entities: Entities = Entities()
    agents: list[str] = []
    answer: str
    steps: list[TraceStep] = []
    artifacts: dict = {}
