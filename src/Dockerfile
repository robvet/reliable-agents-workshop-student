# ============================================================
# Dockerfile — Model Fusion Backend
# Installs dependencies first (cached layer), then copies app
# code. Runs FastAPI via uvicorn on port 8010.
# Build context: project root (not src/).
#   docker build -t modelfusion -f src/Dockerfile .
# ============================================================

FROM python:3.12-slim AS base

WORKDIR /app

# Install dependencies first (layer caching — only rebuilds when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/app/ ./app/

EXPOSE 8010

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8010"]
