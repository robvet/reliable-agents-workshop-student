from pydantic import BaseModel


class TraceStep(BaseModel):
    """One observability trace entry per pipeline hop."""
    agent: str
    action: str
    summary: str
    success: bool = True
    # Structured extras already computed/logged (stdout + OTel span attributes) by the
    # agent - e.g. the NL-2-SQL question, generated SQL, reasoning, row count. Optional
    # so stub agents (no MCP call) can omit it without any special-casing.
    detail: dict[str, str] | None = None
