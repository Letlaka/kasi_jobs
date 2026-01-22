"""validators package re-exports individual validator functions for compatibility.

This package replaces the previous single-module `validators.py`.
"""

from __future__ import annotations

from .consent import require_popia_consent, requires_consent
from .decimal_range import validate_decimal_range
from .email import validate_email_address
from .luhn import luhn_checksum_is_valid
from .phone import validate_phone_number
from .sa_id import validate_sa_id_number
from .sanitize import sanitize_text_field

__all__ = [
    "luhn_checksum_is_valid",
    "require_popia_consent",
    "requires_consent",
    "sanitize_text_field",
    "validate_decimal_range",
    "validate_email_address",
    "validate_phone_number",
    "validate_sa_id_number",
]
