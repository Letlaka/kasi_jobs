from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models

from utilities.models import AuditedModel


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
