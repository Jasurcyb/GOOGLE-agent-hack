# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir google-genai pytest

# Copy all packages and services
COPY packages /app/packages
COPY apps /app/apps
COPY docs /app/docs
COPY scripts /app/scripts
COPY pyproject.toml /app/

# Install packages in editable mode or PYTHONPATH
ENV PYTHONPATH="/app/packages/domain:/app/packages/contracts:/app/packages/code-graph:/app/packages/datahub-adapter:/app/packages/github-adapter:/app/packages/llm-gateway:/app/packages/observability:/app/packages/risk-model:/app/packages/test-fixtures:/app/apps/pr-listener:/app/apps/diff-analyzer:/app/apps/code-intelligence:/app/apps/impact-analyzer:/app/apps/context-orchestrator:/app/apps/risk-engine:/app/apps/reasoning-agent:/app/apps/test-agent:/app/apps/publisher:/app/apps/repo-worker"

EXPOSE 8080

# Default entrypoint runs the PR listener webhook service
CMD ["uvicorn", "pr_listener.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
