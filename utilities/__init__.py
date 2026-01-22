from __future__ import annotations

import contextlib
import os

import structlog

# Bind top-level context values that should be present for all logs produced
# from this application. This happens at import time when `utilities` is
# imported; it's lightweight and defensive.
with contextlib.suppress(Exception):
    structlog.contextvars.bind_contextvars(
        service=os.getenv("SERVICE_NAME", "django_app"),
        environment=os.getenv("ENVIRONMENT", "local"),
    )

from .app_logging import get_logger, log_event  # re-export convenience helpers

__all__ = ["get_logger", "log_event"]
