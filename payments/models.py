from typing import ClassVar

from django.conf import settings
from django.db import models
from jobs.models import Job

from utilities.models import AuditedModel

# Expose AUTH_USER_MODEL safely for type checkers
AUTH_USER_MODEL: str = getattr(settings, "AUTH_USER_MODEL", "accounts.User")


class Payout(AuditedModel):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="payouts")
    seeker = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payouts")

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        # Accessing model attributes like `id` is fine at runtime but mypy
        # may not see them; silence with an inline ignore on attribute access.
        return f"Payout {getattr(self, 'id', None)} for {self.job}"

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["job"]),
            models.Index(fields=["seeker"]),
        ]
