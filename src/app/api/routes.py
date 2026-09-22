"""
API routes for Model Fusion Playground.

This module defines the HTTP endpoints using FastAPI's APIRouter.
Similar to a Controller in ASP.NET or Spring.
"""
# Import declarations (C# directive/ Java declaration equivalent)
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from shapely.geometry import Point, shape

# double-period imports are relative imports from the parent package
# Translates "go in one directory level up, find agents/orchestrator, and
# import the Orchestrator class from it"
from ..agents.orchestrator import Orchestrator
from ..agents.outage_agent import OutageAgent
from ..services.map_asset_service import MapAssetService
from ..services.prompt_library_service import PromptLibraryService
from ..data import Event, GeneratorDatabase
from ..generator import SpatialDataGenerator
from ..tools.weather_client import WeatherClient

from ..models.chat_request import ChatRequest
from ..models.chat_result import ChatResult
from ..models.generate_data_request import GenerateDataRequest
from ..models.request_model import RequestModel
from ..models.create_outage_request import CreateOutageRequest
from ..models.transition_outage_request import TransitionOutageRequest
from ..models.outage_response import OutageResponse
from ..models.stream_event import StreamEvent

##########################################################################
# ApiRoutes - HTTP Endpoint Definitions
##########################################################################
# This class groups related API endpoints together using FastAPI's APIRouter.
#
# In C# terms:
#   - This is like an ASP.NET Controller
#   - APIRouter is like the route collection on a controller
#   - @self.router.get("/health") is like [HttpGet("health")] attribute
#
# Why a class?
#   - Allows constructor injection of dependencies (Orchestrator)
#   - Keeps routes organized in one place
#   - Cleaner than putting all routes in main.py
#   - Makes it easy to unit test routes with mock dependencies
#   - We're building clean architecture principles, not procedural spaghetti:
#   - loose functions and globals scattered in a module with no encapsulation.
#
# Usage in main.py:
#   api_routes = ApiRoutes(orchestrator=orchestrator)
#   app.include_router(api_routes.router)  # Registers all routes
##########################################################################
class ApiRoutes:
    """
    API routes with constructor injection.
    
    Groups all HTTP endpoints and receives dependencies via constructor.
    """


    def __init__(
        self,
        orchestrator: Orchestrator,
        prompt_library_service: PromptLibraryService,
        map_asset_service: MapAssetService,
        weather_client: WeatherClient,
        generator_database: GeneratorDatabase | None = None,
        outage_agent: OutageAgent | None = None,
    ) -> None:
        """
        Initialize routes with injected dependencies.
        
        Args:
            orchestrator: The Orchestrator that handles queries
            prompt_library_service: Prompt template store
            weather_client: NWS alerts client for the /map/weather route
            generator_database: DB access for the synthetic data generator, or
                None when DATABASE_URL is not configured (generator routes then
                return 503 instead of failing app startup).
            outage_agent: Single entry point for outage traffic - the deterministic
                /outages routes call its create_outage/transition/list_outages
                methods, which forward to OutageLifecycleService. None when
                DATABASE_URL is not configured (outage routes then return 503).
        """
        # Store the injected dependencies
        self._orchestrator = orchestrator
        self._prompt_library_service = prompt_library_service
        self._map_asset_service = map_asset_service
        self._weather_client = weather_client
        self._generator_database = generator_database
        self._outage_agent = outage_agent
        self._spatial_data_generator = SpatialDataGenerator()
        
        # Create a FastAPI router - this holds all our route definitions
        # Similar to creating a new controller in ASP.NET
        self.router = APIRouter()
        
        # Register all routes on the router
        self._register_routes()


    def _register_routes(self) -> None:
        """
        Define all HTTP endpoints.
        
        Uses decorator syntax to bind functions to HTTP methods/paths.
        The @self.router decorators are like [HttpGet] / [HttpPost] attributes.
        """
        
        # GET /health - Simple health check endpoint
        # Useful for load balancers and monitoring
        @self.router.get("/health")
        async def health() -> dict:
            return {"status": "ok", "service": "Model Fusion Playground"}

        # GET /prompt-library - Prompt repository for UI bootstrap
        @self.router.get("/prompt-library")
        async def prompt_library() -> dict:
            return self._prompt_library_service.get_all()

        # GET /map/assets - MCP-backed asset coordinates for the frontend map
        @self.router.get("/map/assets")
        async def map_assets() -> dict:
            try:
                assets = await self._map_asset_service.get_assets()
            except RuntimeError as ex:
                raise HTTPException(
                    status_code=502,
                    detail=f"Map asset query failed: {ex}",
                ) from ex

            return {"assets": assets, "count": len(assets)}

        # GET /map/weather - backend-owned NWS alerts for the frontend map, with
        # asset ids that fall inside each alert's polygon so the frontend does not
        # need to reimplement point-in-polygon matching in JS.
        # ?demo=true forces the hardcoded demo preset for this one request only (no
        # state stored) - lets a live demo show a storm on demand without restarting
        # the app or setting weather_demo_mode.
        @self.router.get("/map/weather")
        async def map_weather(demo: bool = False) -> dict:
            try:
                alerts = await self._weather_client.get_active_alerts(force_demo=demo)
                assets = await self._map_asset_service.get_assets()
            except RuntimeError as ex:
                raise HTTPException(
                    status_code=502,
                    detail=f"Weather alerts query failed: {ex}",
                ) from ex

            enriched = []
            for alert in alerts:
                try:
                    polygon = shape(alert["geometry"])
                except Exception:
                    continue
                matching_asset_ids = [
                    asset["id"]
                    for asset in assets
                    if asset.get("lat") is not None
                    and asset.get("lng") is not None
                    and polygon.contains(Point(asset["lng"], asset["lat"]))
                ]
                enriched.append({**alert, "matching_asset_ids": matching_asset_ids})

            return {"alerts": enriched, "count": len(enriched)}

        # POST /chat/stream - live NDJSON stream of the same pipeline.
        # Each line is one StreamEvent JSON: intent -> step (per agent) -> final.
        @self.router.post("/chat/stream")
        async def chat_stream(req: ChatRequest):
            """Stream classify -> plan -> dispatch -> compose as events, one JSON per line."""
            orchestrator = self._orchestrator

            # *********************************************
            # *********  Architectural Insights *************
            # *********************************************
            # Pattern: local stream adapter inside the route handler.
            # - In C#/Java terms, chat_stream is the Controller action and this
            #   function is a private local iterator that adapts domain events to
            #   HTTP stream output.
            # - It consumes Orchestrator.process_request_stream() like an
            #   IAsyncEnumerable<StreamEvent>: one event arrives at a time, in order.
            # - Each iteration writes one NDJSON line, so the client receives progress
            #   incrementally instead of waiting for one final payload.
            # - Separation of concerns: orchestrator decides what happened; this
            #   adapter decides how to serialize and stream each event over HTTP.
            async def event_lines():
                # Empty-database short circuit: skip the whole agent pipeline (which
                # otherwise burns a full ReAct loop only to report nothing found) and
                # point the operator straight at the fix.
                try:
                    assets = await self._map_asset_service.get_assets()
                except RuntimeError:
                    assets = None  # let the normal pipeline surface this failure itself

                if assets is not None and len(assets) == 0:
                    empty_result = ChatResult(
                        answer=(
                            "No data yet - the database is empty. Go to the Synthetic "
                            "Data panel and click \"Regenerate Synthetic Data\" to get started."
                        )
                    )
                    yield StreamEvent(type="final", payload=empty_result.model_dump()).model_dump_json() + "\n"
                    return

                async for event in orchestrator.process_request_stream(
                    RequestModel(user_prompt=req.message, conversation_id=req.conversation_id)
                ):
                    # Actual network write: one event becomes one NDJSON line.
                    yield event.model_dump_json() + "\n"

            return StreamingResponse(
                event_lines(),
                media_type="application/x-ndjson",
                headers={
                    # Browsers MIME-sniff unrecognized content types, which buffers the
                    # response until enough bytes accumulate - the stream then lands all
                    # at once. nosniff disables that so events reach the UI as emitted.
                    "X-Content-Type-Options": "nosniff",
                    # Defeat any intermediary buffering for the same reason.
                    "Cache-Control": "no-cache, no-transform",
                    "X-Accel-Buffering": "no",
                },
            )


        # GET /generator/forecast - pure arithmetic preview, no DB access at all.
        @self.router.get("/generator/forecast")
        async def generator_forecast(
            num_locations: int = 100,
            crew_count: int = 20,
        ) -> dict:
            return {
                "substations": 2,
                "feeders": 4,
                "transformers": 20,
                "service_locations": num_locations,
                "meters": num_locations,
                "crews": crew_count,
                "outages": 3,
            }




        # POST /generator/generate - clears then regenerates synthetic data.
        @self.router.post("/generator/generate")
        async def generator_generate(req: GenerateDataRequest) -> dict:
            if self._generator_database is None:
                raise HTTPException(
                    status_code=503,
                    detail="Data generator is not configured (DATABASE_URL is not set).",
                )
            if not req.confirm:
                raise HTTPException(
                    status_code=400,
                    detail="Set confirm=true to replace existing generated data.",
                )

            session = self._generator_database.create_session()
            try:
                self._spatial_data_generator.execute_spatial_generation(
                    session=session,
                    num_locations=req.num_locations,
                    crew_count=req.crew_count,
                    dry_run=False,
                )
            finally:
                session.close()

            return {"status": "generated"}




        # POST /generator/clear - truncates every table the generator owns.
        @self.router.post("/generator/clear")
        async def generator_clear(confirm: bool = False) -> dict:
            if self._generator_database is None:
                raise HTTPException(
                    status_code=503,
                    detail="Data generator is not configured (DATABASE_URL is not set).",
                )
            if not confirm:
                raise HTTPException(
                    status_code=400,
                    detail="Set confirm=true to clear all generated data.",
                )

            session = self._generator_database.create_session()
            try:
                self._spatial_data_generator.clear_generated_data(session)
                session.commit()
            finally:
                session.close()

            return {"status": "cleared"}


        # POST /outages - deterministic write path, bypasses intent classification
        # and the orchestrator entirely. Plain REST -> OutageAgent -> service -> Postgres.
        @self.router.post("/outages")
        async def create_outage(req: CreateOutageRequest) -> OutageResponse:
            if self._outage_agent is None:
                raise HTTPException(
                    status_code=503,
                    detail="Outage management is not configured (DATABASE_URL is not set).",
                )
            try:
                outage = self._outage_agent.create_outage(
                    asset_id=req.asset_id,
                    event_id=req.event_id,
                    impact_count=req.impact_count,
                    impact_magnitude=req.impact_magnitude,
                )
            except ValueError as ex:
                raise HTTPException(status_code=400, detail=str(ex)) from ex
            return OutageResponse.model_validate(outage)


        # POST /outages/{outage_id}/transition - move an outage to a new status.
        @self.router.post("/outages/{outage_id}/transition")
        async def transition_outage(outage_id: str, req: TransitionOutageRequest) -> OutageResponse:
            if self._outage_agent is None:
                raise HTTPException(
                    status_code=503,
                    detail="Outage management is not configured (DATABASE_URL is not set).",
                )
            try:
                outage = await self._outage_agent.transition(
                    outage_id=outage_id,
                    to_status=req.to_status,
                    note=req.note,
                    crew_id=req.crew_id,
                )
            except ValueError as ex:
                raise HTTPException(status_code=400, detail=str(ex)) from ex
            return OutageResponse.model_validate(outage)


        # GET /outages - list all outages, for the outage management screen.
        @self.router.get("/outages")
        async def list_outages() -> list[OutageResponse]:
            if self._outage_agent is None:
                raise HTTPException(
                    status_code=503,
                    detail="Outage management is not configured (DATABASE_URL is not set).",
                )
            outages = self._outage_agent.list_outages()
            return [OutageResponse.model_validate(o) for o in outages]


        # GET /crews - plain list of crews, for the outage-transition screen's
        # crew-assignment picker.
        @self.router.get("/crews")
        async def list_crews() -> list[dict]:
            if self._outage_agent is None:
                raise HTTPException(
                    status_code=503,
                    detail="Crew lookup is not configured (DATABASE_URL is not set).",
                )
            return self._outage_agent.list_crews()


        # GET /events - plain list of existing events, for the outage-create
        # form's event picker. No service needed: a direct, read-only query,
        # same category as the generator's direct GeneratorDatabase access.
        @self.router.get("/events")
        async def list_events() -> list[dict]:
            if self._generator_database is None:
                raise HTTPException(
                    status_code=503,
                    detail="Event lookup is not configured (DATABASE_URL is not set).",
                )
            session = self._generator_database.create_session()
            try:
                events = session.query(Event).order_by(Event.start_time.desc()).all()
                return [
                    {
                        "event_id": e.event_id,
                        "name": e.name,
                        "severity": e.severity,
                        "region": e.region,
                    }
                    for e in events
                ]
            finally:
                session.close()
