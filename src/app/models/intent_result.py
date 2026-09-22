from pydantic import BaseModel, model_validator

from .entities import Entities
from .intent import Intent


class IntentResult(BaseModel):
    """The ONE model->structure hop. Validated/repaired the instant the model emits it."""
    intent: Intent
    entities: Entities = Entities()
    confidence: float = 0.0
    reasoning: str = ""
    reasoning_pattern: str = ""
    # True when this message continues the prior turn (a follow-up); prior entities carried.
    continues_previous: bool = False
    # Technical detail; set only when intent is ERROR.
    error: str | None = None

    @model_validator(mode="after")
    def _enforce_error_invariant(self) -> "IntentResult":
        # Keeps intent and error in lockstep: a bare ERROR (no detail) downgrades to
        # UNKNOWN; a stray detail on any other intent is dropped.
        if self.intent is Intent.ERROR and not (self.error and self.error.strip()):
            self.intent = Intent.UNKNOWN
        elif self.intent is not Intent.ERROR and self.error:
            self.error = None
        return self
