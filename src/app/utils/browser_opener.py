"""
Browser Opener Utility for FastAPI Applications

This utility class opens a browser window to a specified URL after a delay.
Useful for automatically opening Swagger UI or other documentation when the server starts.

The delay is necessary because FastAPI lifespan fires when the app is created,
but uvicorn may not be listening on the port yet.

Usage in FastAPI lifespan:
    from app.utils.browser_opener import BrowserOpener
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Open browser after server is ready
        BrowserOpener.open_after_delay("http://127.0.0.1:8000/docs", delay_seconds=3.0)
        
        yield
        
        # ... shutdown code ...
    
    app = FastAPI(lifespan=lifespan)

Search for "BROWSER OPENER" in your codebase to find this utility for reuse.
"""

import asyncio
import webbrowser
from typing import Optional


class BrowserOpener:
    """
    Utility class for opening browser windows in FastAPI applications.
    
    Handles the common pattern of opening Swagger UI or documentation
    automatically when the server starts, with a configurable delay to
    ensure the server is ready.
    """
    
    @staticmethod
    async def open_after_delay(
        url: str,
        delay_seconds: float = 3.0,
        background: bool = True
    ) -> None:
        """
        Open a browser window to the specified URL after a delay.
        
        Args:
            url: The URL to open (e.g., "http://127.0.0.1:8000/docs")
            delay_seconds: How long to wait before opening (default: 3.0)
                          This gives uvicorn time to bind to the port
            background: If True, opens browser in background task (non-blocking)
                       If False, waits for delay then opens (blocking)
        
        Note:
            Silently fails on errors - this is best-effort browser opening.
            Won't raise exceptions, making it safe to call in startup.
        """
        if background:
            # Create background task - non-blocking
            asyncio.create_task(BrowserOpener._open_with_delay(url, delay_seconds))
        else:
            # Wait then open - blocking
            await BrowserOpener._open_with_delay(url, delay_seconds)
    
    @staticmethod
    async def _open_with_delay(url: str, delay_seconds: float) -> None:
        """
        Internal helper that waits then opens the browser.
        
        Args:
            url: The URL to open
            delay_seconds: How long to wait before opening
        """
        await asyncio.sleep(delay_seconds)
        try:
            webbrowser.open(url)
        except Exception:
            # Silently fail - this is best-effort browser opening
            pass
    
    @staticmethod
    def open_now(url: str) -> bool:
        """
        Open a browser window to the specified URL immediately (synchronous).
        
        Args:
            url: The URL to open
            
        Returns:
            True if browser opened successfully, False otherwise
        """
        try:
            webbrowser.open(url)
            return True
        except Exception:
            return False
    
    @staticmethod
    def open_swagger_ui(host: str = "127.0.0.1", port: int = 8000) -> bool:
        """
        Convenience method to open FastAPI Swagger UI.
        
        Args:
            host: The host address (default: "127.0.0.1")
            port: The port number (default: 8000)
            
        Returns:
            True if browser opened successfully, False otherwise
        """
        url = f"http://{host}:{port}/docs"
        return BrowserOpener.open_now(url)
    
    @staticmethod
    async def open_swagger_ui_after_delay(
        host: str = "127.0.0.1",
        port: int = 8000,
        delay_seconds: float = 3.0,
        background: bool = True
    ) -> None:
        """
        Convenience method to open FastAPI Swagger UI after a delay.
        
        Args:
            host: The host address (default: "127.0.0.1")
            port: The port number (default: 8000)
            delay_seconds: How long to wait before opening (default: 3.0)
            background: If True, opens in background task (default: True)
        """
        url = f"http://{host}:{port}/docs"
        await BrowserOpener.open_after_delay(url, delay_seconds, background)
    
    @staticmethod
    def open_swagger_ui_background(
        host: str = "127.0.0.1",
        port: int = 8000,
        delay_seconds: float = 3.0
    ) -> None:
        """
        Convenience method to open FastAPI Swagger UI in background (fire-and-forget).
        No await needed - creates background task and returns immediately.
        Use this in async contexts (like FastAPI lifespan) where event loop is available.
        
        Args:
            host: The host address (default: "127.0.0.1")
            port: The port number (default: 8000)
            delay_seconds: How long to wait before opening (default: 3.0)
        """
        url = f"http://{host}:{port}/docs"
        # Create background task - works in async contexts (FastAPI lifespan, etc.)
        asyncio.create_task(BrowserOpener._open_with_delay(url, delay_seconds))

