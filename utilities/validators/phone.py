"""Phone number validator."""

from __future__ import annotations

import re
from typing import Any, cast

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from utilities.app_logging import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName

# E.164-ish simple regex: optional +, digits 7-15
E164_SIMPLE_RE = re.compile(r"^\+?\d{7,15}$")

# Optional runtime import for enhanced phone validation
phonenumbers: object | None = None
try:
    import phonenumbers as _phonenumbers

    phonenumbers = _phonenumbers
except (ImportError, ModuleNotFoundError):  # pragma: no cover - optional dependency
    phonenumbers = None


def validate_phone_number(
    phone_number: str, region: str | None = "ZA", *, strict: bool = False
) -> None:
    """Validate phone number format.

    Lightweight E.164-like check. For stricter checks, enable `strict` and install
    the `phonenumbers` package.
    """
    logger = get_logger(__name__)
    if phone_number is None:
        log_event(
            logger,
            log_name=LogName.SECURITY,
            event_code=EventCode.AUDIT_VALIDATION_PHONE_FAILED,
            event="phone_missing",
            field="phone",
        )
        raise ValidationError(_("Phone number is required."), code="required")

    value = str(phone_number).strip()
    if strict and phonenumbers is not None:
        pn = cast("Any", phonenumbers)
        parsed = pn.parse(value, region)
        if not pn.is_valid_number(parsed):
            raise ValidationError(_("Enter a valid phone number."), code="invalid")
        return

    if not E164_SIMPLE_RE.match(value):
        # Do not include raw value in logs to avoid PII leakage
        log_event(
            logger,
            log_name=LogName.SECURITY,
            event_code=EventCode.AUDIT_VALIDATION_PHONE_FAILED,
            event="phone_invalid_format",
            field="phone",
            reason="format",
        )
        raise ValidationError(
            _("Enter a valid phone number (7-15 digits, optional leading '+')."),
            code="invalid",
        )
