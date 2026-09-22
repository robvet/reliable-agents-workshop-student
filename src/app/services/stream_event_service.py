"""StreamEventService: builds StreamEvent envelopes for the Execution Trace."""
from ..models.stream_event import StreamEvent


class StreamEventService:
    """Single responsibility: wrap a typed payload model into a StreamEvent.

    Public on purpose - the Execution Trace is not Orchestrator-private. Any
    component that needs to emit a trace event calls this instead of
    constructing StreamEvent by hand.
    """

    def build(self, event_type: str, payload_model) -> StreamEvent:
        """Wrap any Pydantic payload model into a StreamEvent envelope."""
        return StreamEvent(type=event_type, payload=payload_model.model_dump(mode="json"))
