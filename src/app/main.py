"""
Model Fusion Playground - Entry point.
"""

##########################################################################
# Architectural Observation - App Factory Pattern
##########################################################################
# The FastAPI app is created in create_app() instead of when Python first loads this file. 
#
# BENEFITS:
#   - Avoids side effects, such as initializing telemetry, creating network 
#     clients, or opening sockets, while this file is being loaded.
#   - Uses a factory convention: Uvicorn, the underlying web server, imports 
#     app.main, then calls create_app()
#   - Familiar to C#/Java readers: this is like a startup composition-root builder method
#   - Improves testability by allowing controlled app construction in tests
##########################################################################

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from .observability.logging_config import LoggingConfig
from .observability.telemetry_service import TelemetryService
from .agents.orchestrator import Orchestrator
from .agents.domain_agent_factory import DomainAgentFactory
from .reasoning.react_reasoning import ReActReasoning
from .context.in_memory_conversation_memory import InMemoryConversationMemory
from .config.config import Settings
from .utils.lifespan_manager import LifespanManager
from .api.routes import ApiRoutes
from .data import GeneratorDatabase
from .services.map_asset_service import MapAssetService
from .tools.weather_client import WeatherClient
from .services.prompt_library_service import PromptLibraryService
from .services.outage_lifecycle_service import OutageLifecycleService
from .services.llm_outage_note_classifier import LlmOutageNoteClassifier
from .tools.mcp_client import McpClient

# create_app() is the entry point for Uvicorn to start the FastAPI app. It builds the composition root, 
# including agents, orchestrator, and routes. Similar to ConfigureServices in C# or Spring Boot's @Configuration class.
def create_app() -> FastAPI:
    LoggingConfig.configure()

    # Telemetry Setup - Provider Initialization
    # We call TelemetryService.setup_telemetry() as an explicit class-qualified startup call.
    TelemetryService.setup_telemetry()

    # Lifespan manager handles startup/shutdown (port cleanup, browser, telemetry flush)
    settings = Settings.get_instance()
    lifespan_manager = LifespanManager(
        port=8010,
        open_browser=settings.open_swagger_browser,
        flush_telemetry=True,
    )

    # FastAPI Application Instance    
    # This creates the FastAPI app. Uvicorn (the web server) picks it up via:
    #   uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
    #
    # The ":create_app --factory" convention means:
    # import app.main, find create_app, call create_app(), and use the returned app.
    #
    # Flow:
    #   1. Uvicorn starts and imports this file (app/main.py)
    #   2. Uvicorn calls create_app()
    #   3. This function creates agents, orchestrator, routes, and app instance
    #   4. Uvicorn starts HTTP server using the returned FastAPI instance
    app = FastAPI(title="Reliable Agents", lifespan=lifespan_manager.lifespan)
    # NOTE: FastAPI request-tracing instrumentation is disabled. The installed
    # opentelemetry-instrumentation-fastapi crashes when naming spans for CORS
    # preflight (OPTIONS) requests under this FastAPI version. LLM/httpx tracing
    # is unaffected. Re-enable once the OTel package supports this FastAPI.
    # FastAPIInstrumentor.instrument_app(app)

    # CORS (dev): allow the local frontend dev server (static files on :5500) to call
    # the API cross-origin. Scoped to localhost only; tighten/replace for production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Prompt library service - suggestive prompt template store
    prompt_library_service = PromptLibraryService()

    # *********************************************
    # *********  Architectural Insights *************
    # *********************************************
    # Pattern: Composition Root. Domain agents are built here and handed to the planner
    # strategy; the strategy is injected into the Orchestrator, which stays ignorant of
    # both the concrete agents and the selection mechanism.
    #
    # MCP data client (NL-2-SQL service). Built once here; injected into the agents
    # that need data access (EventAgent). Disabled -> None -> agents use their stub path.
    mcp_client = (
        McpClient(
            url=settings.mcp_server_url,
            timeout=settings.mcp_timeout,
            connect_timeout=settings.mcp_connect_timeout,
        )
        if settings.mcp_enabled
        else None
    )

    # The data store is mandatory - without it the agents cannot answer anything.
    # Fail fast at startup rather than let a request fault mid-transaction.
    if mcp_client is None:
        raise RuntimeError(
            "MCP client is required but not configured (check mcp_enabled and mcp_server_url)."
        )

    # NWS alerts client (weather feature). Built once here; injected into WeatherAgent
    # and the /map/weather route. demo_mode/demo_preset let this run deterministically
    # without depending on real weather.
    weather_client = WeatherClient(
        base_url=settings.weather_api_base_url,
        timeout=settings.weather_timeout,
        connect_timeout=settings.weather_connect_timeout,
        demo_mode=settings.weather_demo_mode,
        demo_preset=settings.weather_demo_preset,
    )

    # Built ahead of domain_agent_factory (below) since WeatherAgent needs it too.
    map_asset_service = MapAssetService(mcp_client=mcp_client)

    # Data generator - optional; only active when DATABASE_URL is configured.
    # Unlike mcp_client, missing config here does not fail app startup. Built
    # ahead of domain_agent_factory (below) since OutageAgent needs it too.
    generator_database = (
        GeneratorDatabase(database_url=settings.database_url) if settings.database_url else None
    )

    # Outage lifecycle writes reuse the same direct-Postgres connection as the
    # generator (GeneratorDatabase) - not MCP, which is read-only by design.
    outage_lifecycle_service = (
        OutageLifecycleService(generator_database=generator_database)
        if generator_database is not None
        else None
    )

    # Note-triage classifier for outage status transitions - only meaningful when
    # there is somewhere to write an escalated severity, so it's gated the same
    # way as outage_lifecycle_service.
    llm_outage_note_classifier = (
        LlmOutageNoteClassifier() if generator_database is not None else None
    )

    domain_agent_factory = DomainAgentFactory(
        mcp_client=mcp_client,
        weather_client=weather_client,
        map_asset_service=map_asset_service,
        outage_lifecycle_service=outage_lifecycle_service,
        llm_outage_note_classifier=llm_outage_note_classifier,
    )
    reasoning_react = ReActReasoning()

    # Cross-turn conversation memory (in-memory reference store; swap via IConversationMemory).
    conversation_memory = InMemoryConversationMemory()

    # Orchestration Setup - Orchestrator (classify -> reason -> compose)
    orchestrator = Orchestrator(
        reasoning=reasoning_react,
        conversation_memory=conversation_memory,
        domain_agent_factory=domain_agent_factory,
    )

    # API Setup: Define & build route handlers on the APIRouter
    # (map_asset_service already constructed above, ahead of domain_agent_factory)

    # One persistent OutageAgent for the deterministic /outages REST path - built
    # once here, same lifetime as outage_lifecycle_service, unlike the fresh
    # per-step instances the Orchestrator's ReAct loop builds via factory.get().
    outage_agent = domain_agent_factory.get("outage")

    api_routes = ApiRoutes(
        orchestrator=orchestrator,
        prompt_library_service=prompt_library_service,
        map_asset_service=map_asset_service,
        weather_client=weather_client,
        generator_database=generator_database,
        outage_agent=outage_agent,
    )


    # Register API routes on the FastAPI app.
    app.include_router(api_routes.router)

    return app
