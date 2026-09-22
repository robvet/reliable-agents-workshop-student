"""
LifespanManager - Reusable FastAPI lifespan handler.

Handles common startup/shutdown tasks:
- Port cleanup (kill orphan processes)
- Browser auto-open for Swagger UI
- Telemetry flush on shutdown

Usage:
    lifespan_manager = LifespanManager(port=8000, open_browser=True)
    app = FastAPI(lifespan=lifespan_manager.lifespan)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry import trace

from .port_cleanup import PortCleanup
from .browser_opener import BrowserOpener


class LifespanManager:
    """
    Manages FastAPI application lifespan events.
    
    Configurable startup/shutdown behavior for any FastAPI app.
    """

    def __init__(
        self,
        port: int,
        open_browser: bool = True,
        flush_telemetry: bool = True,
    ) -> None:
        """
        Initialize the lifespan manager.
        
        Args:
            port: The port the app runs on (for cleanup)
            open_browser: Whether to auto-open Swagger UI on startup
            flush_telemetry: Whether to flush OpenTelemetry on shutdown
        """
        self._port = port
        self._open_browser = open_browser
        self._flush_telemetry = flush_telemetry

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """
        Async context manager for FastAPI lifespan.
        
        Startup: Cleans port, optionally opens browser
        Shutdown: Flushes telemetry, cleans port
        """
        # --- STARTUP runs when app starts ---
        PortCleanup.kill_process_on_port(self._port)
        if self._open_browser:
            BrowserOpener.open_swagger_ui_background(port=self._port)
        
        yield  # Yield statement is about control flow
               # Upon yield, control is returned to FastAPI and the app code runs
              
               # --- SHUTDOWN runs when when app stops ---
        if self._flush_telemetry:
            self._shutdown_telemetry()
        PortCleanup.kill_process_on_port(self._port)

    def _shutdown_telemetry(self) -> None:
        """Flush pending telemetry data before shutdown."""
        tracer_provider = trace.get_tracer_provider()
        # Similar to Flush() in C# or Java telemetry clients
        if hasattr(tracer_provider, 'shutdown'):
            tracer_provider.shutdown()
