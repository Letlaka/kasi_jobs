"""utilities.validation.validators
Best-practice, single-responsibility validators for reuse.

Principles:
- Single-responsibility functions: return None or raise ValidationError.
- No side-effects: do not log or persist PII.
- Composable small helpers for forms/serializers/models.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils.translation import gettext_lazy as _

# Optional runtime import for enhanced phone validation
phonenumbers: object | None = None
try:
    import phonenumbers as _phonenumbers

    phonenumbers = _phonenumbers
except (ImportError, ModuleNotFoundError):  # pragma: no cover - optional dependency
    phonenumbers = None

# --- Configuration / constants ---
# E.164-ish simple regex: optional +, digits 7-15
E164_SIMPLE_RE = re.compile(r"^\+?\d{7,15}$")

# South African ID: 13 digits (YYMMDD + 7 digits), checksum uses Luhn on first 12 digits.
SA_ID_RE = re.compile(r"^\d{13}$")

# Control characters to strip from text fields (except newline)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]+")


# Luhn helper constant
_LUHN_DOUBLE_SUBTRACT = 9


# --- Validators ---


def validate_phone_number(
    phone_number: str, region: str | None = "ZA", *, strict: bool = False
) -> None:
    """
    Validate phone number format. Lightweight E.164-like check.
    - Accepts numbers like '+27831234567' or '27831234567' or '0831234567'
    - Does NOT perform carrier or country validation.
    - Recommendation: For production, validate with `phonenumbers` package (python-phonenumbers).
    Raises:
        django.core.exceptions.ValidationError
    """
    if phone_number is None:
        raise ValidationError(_("Phone number is required."), code="required")

    value = str(phone_number).strip()
    # If strict mode requested and phonenumbers available, use it for validation.
    if strict and phonenumbers is not None:
        pn = cast("Any", phonenumbers)
        parsed = pn.parse(value, region)
        if not pn.is_valid_number(parsed):
            raise ValidationError(_("Enter a valid phone number."), code="invalid")
        return

    if not E164_SIMPLE_RE.match(value):
        raise ValidationError(
            _("Enter a valid phone number (7-15 digits, optional leading '+')."),
            code="invalid",
        )


def validate_email_address(
    email: str,
    *,
    whitelist_domains: list[str] | None = None,
    blacklist_domains: list[str] | None = None,
) -> None:
    """
    Validate email address using Django's EmailValidator.
    Raises ValidationError on failure.
    """
    if email is None or str(email).strip() == "":
        raise ValidationError(_("Email is required."), code="required")
    validator = EmailValidator(message=_("Enter a valid email address."))
    validator(email)

    # Optional domain restrictions
    if whitelist_domains or blacklist_domains:
        domain = str(email).rsplit("@", 1)[-1].lower()
        lower_whitelist = [d.lower() for d in whitelist_domains] if whitelist_domains else []
        lower_blacklist = [d.lower() for d in blacklist_domains] if blacklist_domains else []
        if lower_whitelist and domain not in lower_whitelist:
            raise ValidationError(_("Email domain not allowed."), code="invalid_domain")
        if lower_blacklist and domain in lower_blacklist:
            raise ValidationError(_("Email domain not allowed."), code="invalid_domain")


def _luhn_checksum_is_valid(number: str) -> bool:
    """Return True if number (digits) passes Luhn checksum.

    Operates on numeric string. Standard Luhn implementation.
    """

    def digits_of(n: str) -> list[int]:
        return [int(d) for d in n]

    digits = digits_of(number)
    checksum = 0
    odd = False
    for digit in reversed(digits):
        d = digit
        if odd:
            d = d * 2
            if d > _LUHN_DOUBLE_SUBTRACT:
                d -= _LUHN_DOUBLE_SUBTRACT
        checksum += d
        odd = not odd
    return checksum % 10 == 0


def validate_sa_id_number(national_id: str) -> None:
    """Validate South African ID number.

    Rules:
    - 13 numeric digits
    - YYMMDD must be a valid date (century heuristic)
    - Luhn checksum must validate
    """
    if national_id is None:
        raise ValidationError(_("ID number is required."), code="required")
    nid = str(national_id).strip()
    if not SA_ID_RE.match(nid):
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
                msg = _("ID number date of birth is in the future.")
                raise ValidationError(msg, code="invalid")
    except ValueError:
        raise ValidationError(_("ID number contains invalid date."), code="invalid") from None

    body = nid[:12]
    if not _luhn_checksum_is_valid(body + nid[12]):
        raise ValidationError(_("ID number checksum is invalid."), code="invalid")


def sanitize_text_field(value: str | None, max_length: int | None = None) -> str:
    """
    Sanitize free-text fields:
    - Trim leading/trailing whitespace
    - Remove control characters (to avoid log injection, CRLF issues)
    - Optionally enforce max_length (raises ValidationError)
    Returns cleaned string.
    """
    if value is None:
        return ""
    s = str(value)
    # Normalize line endings to LF
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # Remove control characters except newline
    s = _CONTROL_CHAR_RE.sub("", s)
    # Collapse repeating whitespace (including newlines) to single spaces.
    # We preserve single newlines from earlier normalization.
    s = re.sub(r"[ \t\f\v]+", " ", s)
    # Trim
    s = s.strip()
    if max_length is not None and len(s) > int(max_length):
        raise ValidationError(_("Text field is too long."), code="max_length")
    return s


def validate_decimal_range(
    value: str | Decimal | int | float,
    min_value: Decimal | None = None,
    max_value: Decimal | None = None,
) -> None:
    """
    Validate that a numeric/Decimal falls within [min_value, max_value] if provided.
    Raises ValidationError otherwise.
    """
    try:
        v = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(
            _("Enter a valid number."),
            code="invalid",
        ) from None

    if min_value is not None and v < min_value:
        raise ValidationError(_("Value is below minimum allowed."), code="min_value")
    if max_value is not None and v > max_value:
        raise ValidationError(_("Value is above maximum allowed."), code="max_value")


def require_popia_consent(*, consent_provided: bool) -> None:
    """
    Simple gate to enforce explicit consent before processing PII.
    In forms/serializers, call this validator before accepting or storing sensitive fields.
    Note: Consent handling must be recorded (audit logging) per POPIA. Do not log sensitive content.
    """
    if not bool(consent_provided):
        raise ValidationError(
            _("User consent required to process personal information."),
            code="consent_required",
        )


def requires_consent(
    field: str = "accept_popia",
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorator to require a consent flag passed in kwargs or as attribute on first arg.

    Usage:
        @requires_consent(field="accept_popia")
        def validate_sa(..., **kwargs):
            ...
    The decorator looks for `field` in kwargs or as attribute on the first positional arg.
    """

    def _decorator(fn: Callable[..., None]) -> Callable[..., None]:
        def _wrapped(*args: object, **kwargs: object) -> None:
            # Check kwargs first
            if isinstance(kwargs, dict) and kwargs.get(field):
                return fn(*args, **kwargs)

            # Then check first arg attribute (e.g., serializer.validated_data)
            if args:
                first = args[0]
                if hasattr(first, field) and getattr(first, field):
                    return fn(*args, **kwargs)

            # No consent found
            raise ValidationError(
                _("User consent required to process personal information."),
                code="consent_required",
            )

        return _wrapped

    return _decorator
