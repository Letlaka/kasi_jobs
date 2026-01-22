from __future__ import annotations

from typing import cast

from django.contrib.auth.models import AbstractUser
from django.db import models

from utilities.models import AuditedModel
from utilities.validators import (
    sanitize_text_field,
    validate_phone_number,
)


class User(AuditedModel, AbstractUser):
    """Custom user model.

    - Keeps Django's built-in fields (username, email, first_name, last_name)
    - Adds a `phone` field and a lightweight `display_name` convenience property.
    """

    phone: models.CharField = models.CharField(max_length=32, blank=True, null=True)
    locked_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    @property
    def display_name(self) -> str:
        """Return a friendly display name for the user.

        Preference: full name, fallback to username.
        """
        full = f"{self.first_name or ''} {self.last_name or ''}".strip()
        # Ensure we always return a concrete `str` (guard against ORM expression unions)
        return str(full) if full else str(self.username)

    def clean(self) -> None:
        """Validate and sanitize user fields before saving.

        - Sanitizes names to remove control characters and trim whitespace.
        - Validates phone number format if provided.
        """
        super().clean()

        # Sanitize name fields (do not log raw PII here)
        # Use cast to satisfy typing when Django supplies expression types
        self.first_name = sanitize_text_field(cast("str | None", self.first_name), max_length=150)
        self.last_name = sanitize_text_field(cast("str | None", self.last_name), max_length=150)

        # Validate phone if present
        if self.phone:
            validate_phone_number(self.phone)
