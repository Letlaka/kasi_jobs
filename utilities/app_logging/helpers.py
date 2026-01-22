from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from .event_codes import EventCode, LogName

LoggerType = structlog.stdlib.BoundLogger


def get_logger(name: str) -> LoggerType:
    """Return a structlog logger with the given name."""
    return structlog.get_logger(name)


def log_event(
    logger: LoggerType,
    *,
    log_name: LogName,
    event_code: EventCode,
    event: str,
    **extra: object,
) -> None:
    """Emit a structured log with minimal inline logic.

    This helper binds only the core semantic fields and delegates
    enrichment (trace ids, schema normalisation, pseudonymisation,
    audit persistence, etc.) to structlog processors and Django
    logging handlers configured elsewhere.
    """
    bound_logger = logger.bind(
        log_name=log_name.value,
        event_id=int(event_code),
        event=event,
    )

    level = "info"
    if isinstance(extra, dict) and "level" in extra:
        level = str(extra.get("level", "info")).lower()

    extra_dict: dict[str, object] = dict(extra) if isinstance(extra, dict) else {}
    extra_dict.pop("level", None)

    log_method = getattr(bound_logger, level, bound_logger.info)
    log_method(event, **extra_dict)
