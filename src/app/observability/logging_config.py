"""
logging_config - Console logging setup for the application.

Logging is one of the three pillars of observability (traces, metrics, logs),
so this module lives alongside telemetry_service.py in the observability package.

SCOPE:
- Configures the ROOT logger for human-readable console output (Rich).
- Tames noisy third-party loggers so the console stays readable.
- Does NOT touch the Azure Monitor / OpenTelemetry export path - that is owned
  entirely by TelemetryService. This is console presentation only.

ORDERING:
- Call LoggingConfig.configure() FIRST at startup (before TelemetryService.setup_telemetry())
  so the root handler exists before anything else logs.
"""
import logging

from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback


class LoggingConfig:
    """
    Console logging configuration for the application.

    Groups all root-logger and third-party noise configuration in one place.
    Stateless: exposes a single static entry point, mirroring TelemetryService.
    """

    @staticmethod
    def configure() -> None:
        """
        Configure console logging for the application.

        Call once at startup, before telemetry setup.
        """
        # Render uncaught exceptions with syntax-highlighted, framed tracebacks.
        # Affects console output only; the Azure Monitor / OpenTelemetry export path is untouched.
        install_rich_traceback(show_locals=False)

        # Set default app log level
        # Options include: DEBUG, INFO, WARNING, ERROR, CRITICAL
        # RichHandler renders the level/time itself, so the format is just the message.
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
        )

        # Suppress verbose logs from underlying libraries to reduce noise and I/O overhead.
        logging.getLogger("azure").setLevel(logging.WARNING)
        logging.getLogger("azure.monitor.opentelemetry.exporter").setLevel(logging.ERROR)
        logging.getLogger("opentelemetry.sdk.trace.export").setLevel(logging.ERROR)
        # Suppress HTTP client request noise
        logging.getLogger("httpx").setLevel(logging.WARNING)
