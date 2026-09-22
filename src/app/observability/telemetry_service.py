"""
TelemetryService - Connects traces and metrics to Azure Application Insights.

================================================================================
OPENTELEMETRY (OTel) OVERVIEW FOR DEVELOPERS
================================================================================

OpenTelemetry is a vendor-neutral observability framework. It has three pillars:

1. TRACES (Spans)
   - Track individual operations (API calls, DB queries, etc.)
   - Spans have parent-child relationships forming a "trace tree"
   - Example: Orchestrator.query -> Orchestrator.call_agent.gpt -> agent.gpt.respond
   - In App Insights: Transaction Search, End-to-end transaction details

2. METRICS (Counters, Histograms, Gauges)
   - Aggregate measurements over time (request counts, latencies)
   - Example: "requests per minute" or "average response time"
   - In App Insights: Metrics Explorer, custom charts/dashboards

3. LOGS
   - Text messages with severity levels (ERROR, WARNING, INFO)
   - Can be correlated with traces for unified debugging
   - In App Insights: Logs (Analytics) blade

KEY OTEL CONCEPTS:
- TracerProvider: Factory that creates Tracers
- Tracer: Creates Spans (one per logical component)
- Span: Single unit of work with start time, end time, attributes
- MeterProvider: Factory that creates Meters
- Meter: Creates metric instruments (counters, histograms)
- Exporter: Sends data to a backend (Azure Monitor, Jaeger, etc.)
- Processor: Batches data before export for efficiency

================================================================================
"""
import logging
from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from azure.monitor.opentelemetry.exporter import (
    AzureMonitorMetricExporter,
    AzureMonitorTraceExporter,
)

from ..config.config import Settings


class TelemetryService:
    """
    Configures OpenTelemetry tracing and metrics with Azure Application Insights.
    
    ARCHITECTURE:
    This is a Singleton - one instance for the entire application.
    Call setup() once at startup (from main.py).
    
    WHAT THIS CLASS DOES:
    1. Creates TracerProvider + Tracer for distributed tracing
    2. Creates MeterProvider + Meter for metrics
    3. Wires Azure Monitor exporters to send data to App Insights
    4. Sets up HTTP auto-instrumentation for LLM API calls
    5. Configures structured logging to correlate logs with traces
    """

    _instance: "TelemetryService | None" = None

    @classmethod
    def get_instance(cls) -> "TelemetryService":
        """
        Return the singleton service instance (created on first access).
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


    # ===========================================================
    # SINGLETON ACCESS - One TelemetryService for the whole app
    # ===========================================================
    # Access the singleton lazily via:
    #   service = TelemetryService.get_instance()
    #   tracer = service.tracer
    #   meter = service.meter
    @staticmethod
    def setup_telemetry() -> None:
        """
        Class-qualified startup entry point for telemetry initialization.
        """
        TelemetryService.get_instance().setup()

    def __init__(self) -> None:
        # These get populated after setup() is called
        # Before setup(): returns no-op implementations (app still works, no telemetry)
        # After setup(): returns configured tracer/meter that export to Azure
        self._tracer: trace.Tracer | None = None
        self._meter: metrics.Meter | None = None
        self._initialized = False

    def setup(self) -> None:
        """
        Configure OpenTelemetry with Azure Monitor exporters.
        
        CALL THIS ONCE AT STARTUP (from main.py).
        
        The setup flow:
        1. Create Resource (identifies this app in App Insights)
        2. Configure TracerProvider -> Tracer (for spans)
        3. Configure MeterProvider -> Meter (for metrics)
        4. Enable HTTP auto-instrumentation (traces LLM API calls)
        5. Enable structured logging (correlates logs with traces)
        """
        settings = Settings.get_instance()

        # Only run once - idempotent
        if self._initialized:
            return

        # No connection string = telemetry disabled
        # App still works, just no data sent to Azure
        if not settings.application_insights_connection_string:
            print("[TELEMETRY] Application Insights connection string not found. Telemetry disabled.")
            return

        print(f"[TELEMETRY] Initializing Application Insights telemetry for {settings.app_name}")

        # =====================================================================
        # RESOURCE: Identifies this application in App Insights
        # =====================================================================
        # All telemetry from this app will be tagged with these attributes.
        # service.name appears as "cloud role name" in App Insights.
        # service.environment lets you filter by dev/staging/production.
        resource = Resource.create(
            {
                "service.name": settings.app_name,
                "service.environment": settings.environment,
            }
        )

        # =====================================================================
        # TRACES (Spans) - Distributed Tracing
        # =====================================================================
        # Spans track individual operations and form parent-child trees.
        # 
        # HOW IT WORKS:
        # 1. AzureMonitorTraceExporter: Converts OTel spans to Azure format
        # 2. BatchSpanProcessor: Batches spans for efficient network usage
        # 3. TracerProvider: Global factory for creating Tracers
        # 4. trace.set_tracer_provider(): Makes this the default for the app
        #
        # AFTER THIS, calling trace.get_tracer(__name__) anywhere returns
        # a Tracer that sends spans to App Insights.
        try:
            trace_exporter = AzureMonitorTraceExporter.from_connection_string(
                conn_str=settings.application_insights_connection_string
            )
            tracer_provider = TracerProvider(resource=resource)
            # BatchSpanProcessor collects spans and sends in batches (more efficient)
            tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
            # Set as global - now trace.get_tracer() uses this provider
            trace.set_tracer_provider(tracer_provider)
            print("[TELEMETRY] Trace exporter configured successfully")
        except Exception as e:
            print(f"[TELEMETRY] ERROR configuring trace exporter: {e}")
            raise

        # =====================================================================
        # METRICS (Counters, Histograms, Gauges)
        # =====================================================================
        # Metrics are aggregate measurements over time.
        #
        # HOW IT WORKS:
        # 1. AzureMonitorMetricExporter: Converts OTel metrics to Azure format
        # 2. PeriodicExportingMetricReader: Exports metrics every N seconds
        # 3. MeterProvider: Global factory for creating Meters
        # 4. metrics.set_meter_provider(): Makes this the default for the app
        #
        # METRIC TYPES (not all used in this app yet):
        # - Counter: Monotonically increasing (request counts)
        # - Histogram: Distribution of values (latency percentiles)
        # - Gauge: Point-in-time value (active connections)
        try:
            metric_exporter = AzureMonitorMetricExporter.from_connection_string(
                conn_str=settings.application_insights_connection_string
            )
            # Reader periodically exports metrics (default: every 60 seconds)
            reader = PeriodicExportingMetricReader(metric_exporter)
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
            metrics.set_meter_provider(meter_provider)
            print("[TELEMETRY] Metric exporter configured successfully")
        except Exception as e:
            print(f"[TELEMETRY] ERROR configuring metric exporter: {e}")
            raise

        # Store references for property access
        self._tracer = trace.get_tracer(__name__)
        self._meter = metrics.get_meter(__name__)
        self._initialized = True

        # =====================================================================
        # HTTP AUTO-INSTRUMENTATION
        # =====================================================================
        # Automatically traces all HTTP calls made via httpx library.
        # 
        # WHY THIS MATTERS:
        # The Azure OpenAI SDK uses httpx under the hood. By instrumenting it,
        # every LLM API call automatically appears as a "dependency" span in
        # App Insights - no manual instrumentation needed.
        #
        # IN APP INSIGHTS: These appear in Application Map and as dependencies
        # in end-to-end transaction details.
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument()
            print("[TELEMETRY] HTTPX instrumentation enabled - HTTP calls will appear in App Insights")
        except Exception as e:
            print(f"[TELEMETRY] WARNING: HTTPX instrumentation failed: {e}")

        # =====================================================================
        # STRUCTURED LOGGING CORRELATION
        # =====================================================================
        # Connects Python's logging module to OpenTelemetry.
        #
        # WHY THIS MATTERS:
        # When you call logging.exception("message") inside a span, the log
        # automatically gets the trace ID and span ID attached. In App Insights,
        # you can click a failed span and see the associated log message.
        #
        # HOW IT WORKS:
        # LoggingHandler captures logs at ERROR level (or above) and exports
        # them to Azure Monitor with trace correlation.
        #
        # USAGE IN CODE:
        #   import logging
        #   except Exception as ex:
        #       logging.exception("Agent call failed")  # Correlated with current span
        try:
            from opentelemetry.sdk._logs import LoggingHandler
            handler = LoggingHandler(level=logging.ERROR)
            logging.getLogger().addHandler(handler)
            print("[TELEMETRY] Structured logging enabled - error logs will correlate with traces")
        except Exception as e:
            print(f"[TELEMETRY] WARNING: Structured logging setup failed: {e}")

    @property
    def tracer(self) -> trace.Tracer:
        """
        Get the configured tracer for creating spans.
        
        USAGE:
            from app.observability.telemetry_service import telemetry_service
            tracer = telemetry_service.tracer
            
            with tracer.start_as_current_span("my_operation") as span:
                span.set_attribute("key", "value")
                do_work()
        
        Returns a no-op tracer if setup() hasn't been called.
        """
        if not self._tracer:
            return trace.get_tracer(__name__)
        return self._tracer

    @property
    def meter(self) -> metrics.Meter:
        """
        Get the configured meter for creating metrics.
        
        USAGE:
            from app.observability.telemetry_service import telemetry_service
            meter = telemetry_service.meter
            
            request_counter = meter.create_counter("requests")
            request_counter.add(1, {"status": "success"})
        
        Returns a no-op meter if setup() hasn't been called.
        """
        if not self._meter:
            return metrics.get_meter(__name__)
        return self._meter




##########################################################################
# Architectural Observation - Provider Abstraction Pattern
##########################################################################
# Telemetry is initialized via an explicit class-qualified startup call:
#
#   TelemetryService.setup_telemetry()
#
# WHY THIS MATTERS:
# Telemetry providers WILL change over time. Today it's Azure Application
# Insights, tomorrow it might be Datadog, Splunk, or a custom solution.
#
# By keeping startup behind this single class-qualified entry point,
# we can swap implementations without changing broader calling code:
#
#   - Local dev: No-op provider (just prints to console)
#   - Azure: Azure Monitor provider (current)
#   - AWS: CloudWatch provider
#   - Testing: Mock provider
#
# To swap providers, change only this file - main.py stays unchanged.
##########################################################################
