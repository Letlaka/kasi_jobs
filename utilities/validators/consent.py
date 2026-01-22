"""Consent enforcement utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from collections.abc import Callable


def require_popia_consent(*, consent_provided: bool) -> None:
    """Raise ValidationError if consent not provided."""
    if not bool(consent_provided):
        raise ValidationError(
            _("User consent required to process personal information."), code="consent_required"
        )


def requires_consent(
    field: str = "accept_popia",
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorator to require a consent flag passed in kwargs or as attribute on first arg."""

    def _decorator(fn: Callable[..., None]) -> Callable[..., None]:
        def _wrapped(*args: object, **kwargs: object) -> None:
            if isinstance(kwargs, dict) and kwargs.get(field):
                return fn(*args, **kwargs)
            if args:
                first = args[0]
                if hasattr(first, field) and getattr(first, field):
                    return fn(*args, **kwargs)
            raise ValidationError(
                _("User consent required to process personal information."), code="consent_required"
            )

        return _wrapped

    return _decorator
