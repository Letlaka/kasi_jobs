"""Luhn helper utilities."""

from __future__ import annotations

_LUHN_DOUBLE_SUBTRACT = 9


def luhn_checksum_is_valid(number: str) -> bool:
    """Return True if number (digits) passes Luhn checksum."""

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
