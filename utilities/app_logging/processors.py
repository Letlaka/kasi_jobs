from __future__ import annotations

import contextlib
import hashlib
import hmac
import os
import socket
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from .event_codes import LogName

if TYPE_CHECKING:
    from collections.abc import MutableMapping

SENSITIVE_KEYS: set[str] = {
    "password",
    "token",
    "authorization",
    "email",
    "phone",
    "national_id",
    "ssn",
    "card_number",
    "address",
    "secret",
}

SERVICE_NAME = os.getenv("SERVICE_NAME", "django_app")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")


def _hmac_value(secret: bytes, value: str) -> str:
    """Return a stable HMAC of the value using the provided secret."""
    return hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()


def redact_sensitive_values(
    _logger: object,  # unused by design: processor API
    _method_name: str,
    event_dict: MutableMapping[str, object],
) -> MutableMapping[str, object]:
    """Redact sensitive values from the event dictionary.

    - Replaces known sensitive keys (shallow) with '[REDACTED]'.
    - Also redacts known nested `user`-dict fields if present.
    """
    for key in list(event_dict.keys()):
        lower_key = key.lower()
        if lower_key in SENSITIVE_KEYS or any(
            token in lower_key for token in ("password", "token", "secret", "authorization", "card")
        ):
            event_dict[key] = "[REDACTED]"

    user_value = event_dict.get("user")
    if isinstance(user_value, dict):
        event_dict["user"] = {
            str(field_key): (
                "[REDACTED]" if str(field_key).lower() in SENSITIVE_KEYS else field_value
            )
            for field_key, field_value in user_value.items()
        }

    return event_dict


def _compute_user_hmac(secret: bytes, identifier: str) -> str:
    """Compute an HMAC digest for the identifier using the given secret."""
    return _hmac_value(secret, identifier)


def pseudonymize_user(
    _logger: object,  # unused by design: processor API
    _method_name: str,
    event_dict: MutableMapping[str, object],
) -> MutableMapping[str, object]:
    """Pseudonymize user identifiers and keep a non-identifying `user` field.

    - Uses HMAC_SECRET_KEY from the environment.
    - Accepts a raw user identifier in keys: user, user_id, actor, email.
    - Binds a `user_hmac` to contextvars and sets `user` to that value.
    """
    secret = os.environ.get("HMAC_SECRET_KEY")
    candidate: object | None = None

    for key in ("user", "user_id", "actor", "email"):
        if key in event_dict:
            candidate = event_dict.get(key)
            break

    if candidate is None:
        return event_dict

    try:
        identifier = str(candidate.pk)  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        try:
            identifier = str(candidate.get_username())  # type: ignore[attr-defined]
        except (AttributeError, TypeError):
            identifier = str(candidate)

    if secret:
        user_hmac = f"hmac_sha256:{_compute_user_hmac(secret.encode('utf-8'), identifier)}"
        with contextlib.suppress(Exception):
            structlog.contextvars.bind_contextvars(user_hmac=user_hmac)

        event_dict["user"] = user_hmac
        event_dict["user_hmac"] = user_hmac

        for key in ("user_id", "actor", "email"):
            event_dict.pop(key, None)
    else:
        # HMAC secret missing: redact identifiers rather than emitting a weak/fixed token.
        redacted_token = "[REDACTED_NO_HMAC]"  # noqa: S105
        for key in ("user", "user_id", "actor", "email"):
            event_dict.pop(key, None)
        event_dict["user"] = redacted_token
        event_dict["user_hmac"] = redacted_token
        # Log a single warning if possible; do not raise to keep logging available.
        with contextlib.suppress(Exception):
            structlog.get_logger(__name__).warning(
                "HMAC_SECRET_KEY not set; identifiers redacted in logs"
            )

    return event_dict


def generate_event_and_trace(
    _logger: object,  # unused by design: processor API
    _method_name: str,
    event_dict: MutableMapping[str, object],
) -> MutableMapping[str, object]:
    """Ensure `trace_id` and `event_uuid` exist in the structured context.

    - `trace_id`: correlation id for request / job.
    - `event_uuid`: unique id for this specific log entry.
    - `event_id`: numeric EVENT CODE is expected to be set upstream; if not,
      we leave it alone and a later normaliser will default to 0.
    """
    to_bind: dict[str, object] = {}
    if "trace_id" not in event_dict:
        to_bind["trace_id"] = uuid.uuid4().hex
    if "event_uuid" not in event_dict:
        to_bind["event_uuid"] = uuid.uuid4().hex

    if to_bind:
        event_dict.update(to_bind)
        with contextlib.suppress(Exception):
            structlog.contextvars.bind_contextvars(**to_bind)

    return event_dict


def normalize_log_schema(
    _logger: object,  # unused by design: processor API
    _method_name: str,
    event_dict: MutableMapping[str, object],
) -> MutableMapping[str, object]:
    """Normalise fields to match the django-app log schema.

    Ensures:
    - timestamp + date_logged
    - log_name (Application/Security/System/Audit)
    - source
    - event_id is numeric (default 0 on failure)
    - service / environment / host
    """
    raw_timestamp = event_dict.get("timestamp")
    now_utc = datetime.now(UTC)

    if isinstance(raw_timestamp, str):
        try:
            parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        except ValueError:
            parsed = now_utc
    else:
        parsed = now_utc

    event_dict["timestamp"] = parsed.isoformat().replace("+00:00", "Z")
    event_dict.setdefault("date_logged", parsed.date().isoformat())

    log_name_value = event_dict.get("log_name")
    if not log_name_value:
        logger_name = str(event_dict.get("logger", ""))
        if logger_name.startswith("django.security") or "security" in logger_name:
            log_name_value = LogName.SECURITY.value
        elif logger_name.startswith("django") or logger_name.startswith("system"):
            log_name_value = LogName.SYSTEM.value
        else:
            log_name_value = LogName.APPLICATION.value
        event_dict["log_name"] = log_name_value

    event_dict.setdefault("source", event_dict.get("logger", SERVICE_NAME))

    event_id_value = event_dict.get("event_id")
    if not isinstance(event_id_value, int):
        try:
            event_dict["event_id"] = int(str(event_id_value)) if event_id_value is not None else 0
        except (TypeError, ValueError):
            event_dict["event_id"] = 0

    event_dict.setdefault("service", SERVICE_NAME)
    event_dict.setdefault("environment", ENVIRONMENT)
    event_dict.setdefault("host", socket.gethostname())

    return event_dict
