from pydantic import BaseModel

from .plan_step import PlanStep


class ExecutionPlan(BaseModel):
    """Model-proposed, code-validated plan: the ordered/dependent steps for ONE request.

    The planner (model) authors this; deterministic code validates it against the
    allow-list before the executor runs it. Order is a property of the request, not
    of the intent - which is why it lives here and not in a static routing table.
    """
    steps: list[PlanStep] = []
