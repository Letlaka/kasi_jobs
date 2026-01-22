"""
Unit tests for validators (pytest + Django).
Run: pytest -q
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from utilities.validators import (
    require_popia_consent,
    sanitize_text_field,
    validate_decimal_range,
    validate_email_address,
    validate_phone_number,
    validate_sa_id_number,
)


def test_validate_phone_ok() -> None:
    validate_phone_number("+27831234567")
    validate_phone_number("0831234567")
    validate_phone_number("27831234567")


def test_validate_phone_bad() -> None:
    with pytest.raises(ValidationError):
        validate_phone_number("abc")
    with pytest.raises(ValidationError):
        validate_phone_number("123")


def test_validate_email_ok() -> None:
    validate_email_address("user@example.com")


def test_validate_email_bad() -> None:
    with pytest.raises(ValidationError):
        validate_email_address("no-at-sign")


def test_sa_id_ok() -> None:
    # Example: 8001015009087 is a commonly used test SA ID (1980-01-01)
    validate_sa_id_number("8001015009087")


def test_sa_id_bad_format() -> None:
    with pytest.raises(ValidationError):
        validate_sa_id_number("123")


def test_sanitize_text() -> None:
    if sanitize_text_field(" hello \n") != "hello":
        raise AssertionError("sanitize_text_field did not trim/normalize as expected")
    with pytest.raises(ValidationError):
        sanitize_text_field("x" * 5000, max_length=10)


def test_decimal_range() -> None:
    validate_decimal_range("10.5", min_value=Decimal("0"), max_value=Decimal("100"))
    with pytest.raises(ValidationError):
        validate_decimal_range("abc", min_value=Decimal("0"))


def test_require_consent() -> None:
    with pytest.raises(ValidationError):
        require_popia_consent(consent_provided=False)
