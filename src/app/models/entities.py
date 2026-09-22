from pydantic import BaseModel


class Entities(BaseModel):
    """Typed, known entity slots extracted from a message. Fully structured - no freeform.

    Every slot is an explicit, nullable field so the model can only populate known
    entities and downstream code reads them by name (e.g. entities.asset_id).
    """
    asset_id: str | None = None
    feeder: str | None = None
    substation: str | None = None
    location: str | None = None
    event_id: str | None = None
    # Set by the intent classifier (one model judgment, not re-decided per ReAct
    # step) when the question asks about assets affected/impacted/downstream of
    # asset_id. See docs/business-rules/fixed-graph-traversal-query-for-assets.md.
    needs_downstream_assets: bool = False
