from __future__ import annotations

import logging
from collections.abc import Callable, MutableMapping
from typing import Any

import structlog

from utilities.app_logging.processors import (
    generate_event_and_trace,
    normalize_log_schema,
    pseudonymize_user,
    redact_sensitive_values,
)

from .env import env

Processor = Callable[[Any, str, MutableMapping[str, Any]], Any]

SHARED_PRE_PROCESSORS: list[Processor] = [
    generate_event_and_trace,
    pseudonymize_user,
    redact_sensitive_values,
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
    normalize_log_schema,
]

LOG_RENDER_MODE = "console"

# Structlog / django-structlog flags
DJANGO_STRUCTLOG_IP_LOGGING_ENABLED = env.bool("DJANGO_STRUCTLOG_IP_LOGGING_ENABLED", default=True)
DJANGO_STRUCTLOG_STATUS_4XX_LOG_LEVEL = logging.WARNING
DJANGO_STRUCTLOG_STATUS_5XX_LOG_LEVEL = logging.ERROR

# When audit logging falls back to plain handlers, allow opt-out via env
LOGGING_AUDIT_FALLBACK_ENABLED = env.bool("LOGGING_AUDIT_FALLBACK_ENABLED", default=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "application_log": {
            "()": "utilities.app_logging.filters.LogNameFilter",
            "log_name": "Application",
        },
        "security_log": {
            "()": "utilities.app_logging.filters.LogNameFilter",
            "log_name": "Security",
        },
        "system_log": {
            "()": "utilities.app_logging.filters.LogNameFilter",
            "log_name": "System",
        },
        "audit_log": {
            "()": "utilities.app_logging.filters.LogNameFilter",
            "log_name": "Audit",
        },
    },
    "formatters": {
        "json_formatter": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
            "foreign_pre_chain": SHARED_PRE_PROCESSORS,
        },
        "safe_json": {
            "()": "utilities.app_logging.formatters.SafeJSONFormatter",
        },
        "plain_console": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(),
            "foreign_pre_chain": SHARED_PRE_PROCESSORS,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain_console",
            "level": "WARNING",
        },
        "application_file": {
            "class": "utilities.app_logging.handlers.PrettyJSONArrayFileHandler",
            "formatter": "safe_json",
            "filename": "logs/application.log",
            "when": "midnight",
            "interval": 1,
            "backupCount": 14,
            "filters": ["application_log"],
        },
        "security_file": {
            "class": "utilities.app_logging.handlers.PrettyJSONArrayFileHandler",
            "formatter": "safe_json",
            "filename": "logs/security.log",
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "filters": ["security_log"],
        },
        "system_file": {
            "class": "utilities.app_logging.handlers.PrettyJSONArrayFileHandler",
            "formatter": "safe_json",
            "filename": "logs/system.log",
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "filters": ["system_log"],
        },
        "audit_file": {
            "class": "utilities.app_logging.handlers.PrettyJSONArrayFileHandler",
            "formatter": "safe_json",
            "filename": "logs/audit.log",
            "when": "midnight",
            "interval": 1,
            "backupCount": 365,
            "filters": ["audit_log"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "utilities.application": {
            "handlers": ["application_file"],
            "level": "INFO",
            "propagate": False,
        },
        "utilities.security": {
            "handlers": ["security_file"],
            "level": "INFO",
            "propagate": False,
        },
        "utilities.system": {
            "handlers": ["system_file"],
            "level": "INFO",
            "propagate": False,
        },
        "utilities.audit": {
            "handlers": ["audit_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
