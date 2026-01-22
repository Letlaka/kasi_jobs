"""South African ID validator."""

from __future__ import annotations

from datetime import datetime

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from utilities.app_logging import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName

from .luhn import luhn_checksum_is_valid

# South African ID: 13 digits (YYMMDD + 7 digits)
SA_ID_RE = __import__("re").compile(r"^\d{13}$")


def validate_sa_id_number(national_id: str) -> None:
    """Validate South African ID number.

    Checks format, date of birth (century heuristic), and Luhn checksum.
    """
    logger = get_logger(__name__)
    if national_id is None:
        log_event(
            logger,
            log_name=LogName.SECURITY,
            event_code=EventCode.AUDIT_VALIDATION_SA_ID_FAILED,
            event="sa_id_missing",
            field="national_id",
        )
        raise ValidationError(_("ID number is required."), code="required")
    nid = str(national_id).strip()
    if not SA_ID_RE.match(nid):
        log_event(
            logger,
            log_name=LogName.SECURITY,
            event_code=EventCode.AUDIT_VALIDATION_SA_ID_FAILED,
            event="sa_id_bad_format",
            field="national_id",
        )
        raise ValidationError(_("ID number must be 13 digits."), code="invalid")

    dob_part = nid[:6]
    try:
        year = int(dob_part[0:2])
        month = int(dob_part[2:4])
        day = int(dob_part[4:6])
        now = datetime.utcnow()
        current_two_digit = now.year % 100
        century = 1900 if year > current_two_digit else 2000
        full_year = century + year
        dob = datetime(full_year, month, day)
        if dob > now:
            dob = datetime(full_year - 100, month, day)
            if dob > now:
                raise ValidationError(
                    _("ID number date of birth is in the future."), code="invalid"
                )
    except ValueError:
        log_event(
            logger,
            log_name=LogName.SECURITY,
            event_code=EventCode.AUDIT_VALIDATION_SA_ID_FAILED,
            event="sa_id_invalid_date",
            field="national_id",
        )
        raise ValidationError(_("ID number contains invalid date."), code="invalid") from None

    body = nid[:12]
    if not luhn_checksum_is_valid(body + nid[12]):
        log_event(
            logger,
            log_name=LogName.SECURITY,
            event_code=EventCode.AUDIT_VALIDATION_SA_ID_FAILED,
            event="sa_id_checksum_failed",
            field="national_id",
        )
        raise ValidationError(_("ID number checksum is invalid."), code="invalid")
