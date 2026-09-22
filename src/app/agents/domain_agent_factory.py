from .base_domain_agent import BaseDomainAgent
from .asset_agent import AssetAgent
from .crew_agent import CrewAgent
from .direct_query_agent import DirectQueryAgent
from .event_agent import EventAgent
from .outage_agent import OutageAgent
from .reliability_agent import ReliabilityAgent
from .weather_agent import WeatherAgent
from ..services.map_asset_service import MapAssetService
from ..services.outage_lifecycle_service import OutageLifecycleService
from ..services.llm_outage_note_classifier import LlmOutageNoteClassifier
from ..tools.i_mcp_client import IMcpClient
from ..tools.weather_client import WeatherClient


class DomainAgentFactory:
    # *********************************************
    # *********  Architectural Insights *************
    # *********************************************
    # Patterns: Factory + Registry, used as a Composition Root collaborator.
    # - Owns intent-key -> concrete domain agent resolution, so the Orchestrator
    #   depends on this abstraction instead of newing up concrete agents
    #   (Dependency Inversion).
    # - Lifetime: a NEW agent instance is built on every get() call. No shared
    #   singleton agents, no cross-request instance state possible. Only the
    #   injected clients (mcp_client, weather_client, map_asset_service) are
    #   shared - each is itself stateless/reentrant (see their own docstrings).
    """Resolves the concrete domain agent for a given routing key (Phase 0: stubs)."""

    def __init__(
        self,
        mcp_client: IMcpClient,
        weather_client: WeatherClient,
        map_asset_service: MapAssetService,
        outage_lifecycle_service: OutageLifecycleService | None = None,
        llm_outage_note_classifier: LlmOutageNoteClassifier | None = None,
    ) -> None:
        """Store the injected clients; no agents are constructed yet.

        mcp_client is required and injected into the data agents (direct_query,
        asset, event, crew, reliability). main.py fails fast at startup
        if it cannot be built. weather_client/map_asset_service are injected into
        the weather agent. outage_lifecycle_service/llm_outage_note_classifier are
        injected into OutageAgent for its deterministic write path and note-triage;
        both None when DATABASE_URL is not set.
        """
        self._mcp_client = mcp_client
        self._weather_client = weather_client
        self._map_asset_service = map_asset_service
        self._outage_lifecycle_service = outage_lifecycle_service
        self._llm_outage_note_classifier = llm_outage_note_classifier

        # Class references only (never instantiated) - lets catalog() read the
        # class-level `description` attribute without building an agent.
        self._classes: dict[str, type[BaseDomainAgent]] = {
            "direct_query": DirectQueryAgent,
            "asset": AssetAgent,
            "event": EventAgent,
            "outage": OutageAgent,
            "crew": CrewAgent,
            "reliability": ReliabilityAgent,
            "weather": WeatherAgent,
        }

    def get(self, name: str) -> BaseDomainAgent | None:
        """Build and return a fresh agent instance for a routing key, or None if unknown."""
        match name:
            case "direct_query":
                return DirectQueryAgent(mcp_client=self._mcp_client)
            case "asset":
                return AssetAgent(mcp_client=self._mcp_client)
            case "event":
                return EventAgent(mcp_client=self._mcp_client)
            case "outage":
                return OutageAgent(
                    mcp_client=self._mcp_client,
                    outage_lifecycle_service=self._outage_lifecycle_service,
                    llm_outage_note_classifier=self._llm_outage_note_classifier,
                )
            case "crew":
                return CrewAgent(mcp_client=self._mcp_client)
            case "reliability":
                return ReliabilityAgent(mcp_client=self._mcp_client)
            case "weather":
                return WeatherAgent(
                    weather_client=self._weather_client,
                    map_asset_service=self._map_asset_service,
                )
            case _:
                return None

    def catalog(self, names: list[str] | None = None) -> dict[str, str]:
        """Return {agent_name: description} for the planner. Optionally filtered to `names`."""
        keys = names if names is not None else list(self._classes.keys())
        return {
            key: getattr(self._classes[key], "description", key)
            for key in keys
            if key in self._classes
        }
