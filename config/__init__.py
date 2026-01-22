"""Lightweight config package initializer.

Import the Celery app only when Celery is installed. This avoids forcing
`celery` to be a runtime dependency for simple CLI scripts that import
`config.settings.env`.
"""

try:  # pragma: no cover - optional celery
    from .celery import app as celery_app

    __all__ = ["celery_app"]
except (ImportError, AttributeError):  # pragma: no cover - allow scripts to run without celery
    __all__ = []
