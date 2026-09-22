from pydantic import BaseModel, model_validator

from .entities import Entities
from .intent import Intent


class IntentResult(BaseModel):
    """ The output of intent classification: the model has reads the user's
    unstructured message, determined the intent, and produced structured output,
    which includes the recognized intent, extracted entities, confidence score, and reasoning details.
    
    From this point downstream, the system has a deterministic guarantee that intent, entities, confidence, 
    and reasoning fields are validated and consistent.
    """
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
        # Rule: an ERROR intent must always carry a non-empty error message, otherwise it's reclassified as UNKNOWN.
        # An error with no explanation gives downstream code (logging, user-facing messages, retries) nothing to act 
        # on — so it's treated as an unknown intent instead
        if self.intent is Intent.ERROR and not (self.error and self.error.strip()):
            self.intent = Intent.UNKNOWN
        elif self.intent is not Intent.ERROR and self.error:
            self.error = None
        return self
