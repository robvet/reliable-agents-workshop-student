from pydantic import BaseModel


class PlanStep(BaseModel):
    """One step in a per-request execution plan: which agent to run.

    Steps run in the order the planner lists them.
    """
    id: str
    agent: str
