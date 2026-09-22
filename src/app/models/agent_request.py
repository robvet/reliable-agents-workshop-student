from pydantic import BaseModel

from .entities import Entities


class AgentRequest(BaseModel):
    """Request handed to a single domain agent."""
    agent: str
    action: str = "handle"
    params: dict = {}
    # Typed scope extracted at intent time (region, asset, event, ...). Every agent
    # receives it; each reads only the slots relevant to its domain.
    entities: Entities = Entities()
    # The user's unchanged words for the direct-query agent.
    user_prompt: str = ""
