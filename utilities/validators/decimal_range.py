"""Decimal range validator."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from utilities.app_logging import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName


def validate_decimal_range(
    value: str | Decimal | int | float,
    min_value: Decimal | None = None,
    max_value: Decimal | None = None,
) -> None:
    """Validate that a numeric/Decimal falls within optional bounds."""
    logger = get_logger(__name__)
    try:
        v = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        log_event(
            logger,
            log_name=LogName.SECURITY,
            event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
            event="decimal_parse_failed",
            field="number",
        )
        raise ValidationError(_("Enter a valid number."), code="invalid") from None

    if min_value is not None and v < min_value:
        raise ValidationError(_("Value is below minimum allowed."), code="min_value")
    if max_value is not None and v > max_value:
        raise ValidationError(_("Value is above maximum allowed."), code="max_value")
