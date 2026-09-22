from pydantic import BaseModel


class StreamEvent(BaseModel):
    """One event in the live NDJSON stream for a single request.

    Serialized one-per-line by POST /chat/stream. `type` tells the UI how to render:
      - "intent" : classification result (intent, confidence, reasoning, entities)
      - "plan"   : the ExecutionPlan, in execution order, before any agent runs
      - "step"   : one agent's TraceStep, emitted as that step completes
      - "final"  : the composed ChatResult (the answer)
      - "error"  : a processing failure
    `payload` is the JSON-safe body for that event type.
    """
    type: str
    payload: dict = {}
