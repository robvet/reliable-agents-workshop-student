# syntax=docker/dockerfile:1
#
# mcp_sql container image (disposable Phase 0 sandbox — see AGENTS.md).
#
# Two stages:
#   1. pgedge-build — compiles the pgEdge Postgres MCP *Linux* binary from
#      source. The vendored ./pgedge-postgres-mcp is a macOS arm64 Mach-O
#      binary and CANNOT run in a Linux container, so we build the Linux one.
#      Pinned to the same release the local binary reports (v1.0.0).
#   2. runtime — Python 3.11 image that runs server.py (FastMCP Streamable
#      HTTP on :8000) and spawns the pgEdge binary as a stdio subprocess.
#
# Build in the cloud (e.g. `az acr build`), not on the corp network: pip inside
# the image pulls from public PyPI, and the local corp feed (set only in the
# host's global pip.conf) does not exist inside the build.

# ---- Stage 1: build the pgEdge Postgres MCP binary (Go) for Linux ----
FROM golang:1.24-bookworm AS pgedge-build
ARG PGEDGE_REF=v1.0.0
RUN git clone --depth 1 --branch "${PGEDGE_REF}" \
    https://github.com/pgEdge/pgedge-postgres-mcp.git /src
WORKDIR /src
RUN go build -o /out/pgedge-postgres-mcp ./cmd/pgedge-pg-mcp-svr

# ---- Stage 2: Python runtime ----
FROM python:3.11-slim AS runtime
WORKDIR /app

# Linux pgEdge binary from the builder stage.
COPY --from=pgedge-build /out/pgedge-postgres-mcp /app/pgedge-postgres-mcp

# App sources. py-modules in pyproject.toml must be present at install time,
# so copy them before `pip install .`. prompts/ is read at import by nl2sql.py.
COPY pyproject.toml ./
COPY config.py telemetry.py upstream.py nl2sql.py server.py ./
COPY prompts/ ./prompts/
RUN pip install --no-cache-dir .

# Point upstream.py at the Linux binary (default is ./pgedge-postgres-mcp).
ENV PGEDGE_BIN=/app/pgedge-postgres-mcp \
    PYTHONUNBUFFERED=1

# FastMCP Streamable HTTP transport, mounted at /mcp.
EXPOSE 8000
CMD ["python", "server.py"]
