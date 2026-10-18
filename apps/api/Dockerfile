# syntax=docker/dockerfile:1
# Multi-stage build for the Curiosity API. Build context: repository root.

FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
WORKDIR /app

# --- dev: all dependencies, source mounted by docker compose -------------------
FROM base AS dev
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-install-project
CMD ["sh", "-c", "alembic upgrade head && uvicorn --factory app.main:create_app --host 0.0.0.0 --port 8000 --reload"]

# --- build: production dependencies only --------------------------------------
FROM base AS build
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps/api/ ./
RUN uv sync --frozen --no-dev

# --- runtime: slim, non-root ----------------------------------------------------
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
RUN groupadd --system app && useradd --system --gid app --no-create-home app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build /app /app
USER app
EXPOSE 8000
# Release step (run separately per deploy): alembic upgrade head
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]
