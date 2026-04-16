# syntax=docker/dockerfile:1.4
# Stage 1: Base build stage
FROM python:3.13-slim AS builder
## Builder: use `uv` to create a reproducible environment and install project

# Copy uv binary from official uv image (pin to a version)
COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /uvx /bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_DEV=1

# Create a dedicated non-root user in the builder with a fixed UID/GID
# This ensures parity between builder and final image ownerships
RUN groupadd -g 1000 appuser \
    && useradd -u 1000 -g appuser -m -r -s /usr/sbin/nologin appuser

# Install minimal system packages required for building some Python packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata first for better cache locality
COPY pyproject.toml /app/

# Use cache mount for uv to speed up repeated builds (requires BuildKit)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync

# Copy source and perform a final sync to ensure project is installed
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync

## Final image: copy the created virtual environment only
FROM python:3.13-slim

# Copy application and environment from builder

# Create a dedicated non-root user, copy the app, and set ownership
RUN groupadd -g 1000 appuser \
    && useradd -u 1000 -g appuser -m -r -s /usr/sbin/nologin appuser

# Copy the application from builder and set ownership in one step to avoid extra chown layer
COPY --from=builder --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

USER appuser

EXPOSE 8000

# Lightweight healthcheck endpoint (adjust path if different)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/healthz || exit 1

# Run the ASGI application using uvicorn from the uv-managed environment
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]