"""Text sanitization utilities."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from utilities.app_logging import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName

# Control characters to strip from text fields (except newline)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]+")


def sanitize_text_field(value: str | None, max_length: int | None = None) -> str:
    """Sanitize free-text fields and optionally enforce max length."""
    if value is None:
        return ""
    s = str(value)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _CONTROL_CHAR_RE.sub("", s)
    s = re.sub(r"[ \t\f\v]+", " ", s)
    s = s.strip()
    if max_length is not None and len(s) > int(max_length):
        logger = get_logger(__name__)
        # Log that truncation/length violation happened; do not log the text itself
        log_event(
            logger,
            log_name=LogName.AUDIT,
            event_code=EventCode.AUDIT_VALIDATION_SANITIZE_TRUNCATED,
            event="text_too_long",
            field="text",
            length=len(s),
        )
        raise ValidationError(_("Text field is too long."), code="max_length")
    return s
