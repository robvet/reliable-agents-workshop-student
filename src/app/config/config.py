from typing import ClassVar

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application configuration.

    Values are loaded from environment variables / .env file by default.
    """

    # Pydantic v2 settings config
    # Note env_file=".env". This is the equivalent of a manual call to load_dotenv() in v1.
    # On that parameter, Pydantic reads and parses .env internally.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    _instance: ClassVar["Settings | None"] = None

    azure_openai_endpoint: str = Field(..., env="AZURE_OPENAI_ENDPOINT")
    # Legacy deployment name; no longer used by the live pipeline (intent uses
    # intent_slm_deployment). Optional so a missing/renamed env var can't block boot.
    azure_openai_deployment_gpt: str | None = Field(default=None, env="AZURE_OPENAI_DEPLOYMENT_GPT")

    # Intent classifier SLM deployment (Responses API via Agent Framework).
    # Accepts either spelling of the env var (SLM or the legacy SML typo).
    intent_slm_deployment: str = Field(
        ...,
        validation_alias=AliasChoices("INTENT_SLM_DEPLOYMENT", "INTENT_SML_DEPLOYMENT"),
    )

    # Inference/synthesis LM used for response composition (the final answer-writing hop).
    # Kept separate from the intent SLM so the answer-writer can be scaled independently.
    # Optional: falls back to intent_slm_deployment when unset, so boot never breaks.
    inference_lm_deployment: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INFERENCE_LM_DEPLOYMENT", "INFERENCING_LM_DEPLOYMENT"),
    )

    # MCP (NL-2-SQL data server). Endpoint is environment-specific — required, no default.
    mcp_server_url: str = Field(...)

    # Per-call timeout (seconds) for MCP tool invocations.
    mcp_timeout: float = Field(60.0)

    # Timeout (seconds) for establishing the MCP session.
    mcp_connect_timeout: float = Field(10.0)

    # When false, MCP-backed agents fall back to stub data.
    mcp_enabled: bool = Field(True)

    # NWS (National Weather Service) alerts API — backend-owned weather integration.
    weather_api_base_url: str = Field("https://api.weather.gov")
    weather_timeout: float = Field(5.0)
    weather_connect_timeout: float = Field(3.0)

    # When true, WeatherClient returns a fabricated alert instead of calling NWS —
    # mirrors mcp_enabled's stub-fallback pattern, for reliable demos.
    weather_demo_mode: bool = Field(False)
    weather_demo_preset: str = Field("north_region_severe_tstorm")

    # Direct PostgreSQL connection string for the synthetic data generator only.
    # The rest of the app reads/writes exclusively through MCP; this is a separate
    # path used solely by the admin data-generator feature.
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")

    # Gemini (reference agent - optional; only needed if GeminiAgent is instantiated)
    gemini_api_key: str | None = Field(default=None, env="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-3-pro-preview", env="GEMINI_MODEL")

    # Anthropic (reference agent - optional; only needed if AnthropicAgent is instantiated)
    anthropic_api_key: str | None = Field(default=None, env="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-3-5-sonnet-20241022", env="ANTHROPIC_MODEL")

    # Total request timeout (seconds) for all model API calls.
    # Configurable via AGENT_TIMEOUT in .env — applies to both respond() and run_turn() paths.
    agent_timeout: float = Field(120.0, env="AGENT_TIMEOUT")

    # Per-model timeout overrides (optional). Falls back to agent_timeout if not set.
    agent_timeout_gpt: float | None = Field(default=None, env="AGENT_TIMEOUT_GPT")
    agent_timeout_gemini: float | None = Field(default=None, env="AGENT_TIMEOUT_GEMINI")
    agent_timeout_anthropic: float | None = Field(default=None, env="AGENT_TIMEOUT_ANTHROPIC")

    # TCP handshake timeout (seconds) — how long httpx waits to establish a connection
    # to the remote server. Fails fast if the endpoint is unreachable.
    agent_connect_timeout: float = Field(30.0, env="AGENT_CONNECT_TIMEOUT")

    # Application Insights connection string, e.g.:
    # "InstrumentationKey=...;IngestionEndpoint=..."
    # Made optional so the app can run without telemetry while we debug env issues.
    # Application Insights connection string
    # Note: .env file uses APPLICATIONINSIGHTS_CONNECTION_STRING (no underscores)
    application_insights_connection_string: str | None = Field(
        default=None,
        validation_alias="APPLICATIONINSIGHTS_CONNECTION_STRING",
    )

    app_name: str = "Reliable Agents"
    # Accept both APP_ENVIRONMENT and app_environment for flexibility.
    environment: str = Field("dev", env=["APP_ENVIRONMENT", "app_environment"])

    # Show exception details in streamed UI errors. Keep false outside local development.
    show_verbose_errors: bool = Field(False, validation_alias="SHOW_VERBOSE_ERRORS")

    # Whether to auto-open the Swagger UI in a browser on startup. Default off.
    open_swagger_browser: bool = Field(False, env="OPEN_SWAGGER_BROWSER")

    # Optional API key support if you ever decide not to use DefaultAzureCredential.
    # This also prevents validation errors if AZURE_OPENAI_API_KEY is present.
    azure_openai_api_key: str | None = Field(default=None, env="azure_openai_api_key")

    def get_agent_timeout(self, agent_name: str) -> float:
        """Return per-model timeout if set, otherwise the shared agent_timeout."""
        per_model = getattr(self, f"agent_timeout_{agent_name}", None)
        return per_model if per_model is not None else self.agent_timeout

    @classmethod
    def get_instance(cls) -> "Settings":
        """Lazily create and return the shared settings instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance



