from ..models.intent import Intent


class RoutingMap:
    """Allow-list (NOT an execution order). Answers the one question an intent CAN
    answer: "which agents is this intent permitted to use?" The per-request order and
    dependencies are decided by the planner and checked against this set - the model
    may never reach for an agent outside its intent's allow-list.
    """

    _MAP: dict[Intent, list[str]] = {
        Intent.EVENT_RESPONSE: ["asset", "event", "outage", "crew", "weather"],
        Intent.SITUATIONAL_AWARENESS: ["event", "crew"],
        Intent.RELIABILITY: ["reliability", "asset"],
        Intent.MAJOR_EVENT: ["event", "asset", "weather"],
        Intent.CROSS_DOMAIN: ["reliability", "event", "crew", "asset"],
        # Broad in-domain questions go straight to the direct-query agent.
        Intent.DOMAIN_LOOKUP: ["asset", "event", "crew", "reliability"],
        Intent.UNKNOWN: [],
        # ERROR dispatches no agents: on a technical fault we short-circuit to a soft
        # apology in Orchestrator.compose() rather than running the domain pipeline.
        Intent.ERROR: [],
    }

    @classmethod
    def allowed_agents(cls, intent: Intent) -> list[str]:
        """Return the agents this intent is permitted to use ([] when none)."""
        return cls._MAP.get(intent, [])
