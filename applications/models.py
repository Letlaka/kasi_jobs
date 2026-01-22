from typing import ClassVar, cast

from django.conf import settings
from django.db import models
from jobs.models import Job

from utilities.models import AuditedModel
from utilities.validators import sanitize_text_field, validate_decimal_range

# Expose AUTH_USER_MODEL via getattr to avoid import-time attribute checks
AUTH_USER_MODEL: str = getattr(settings, "AUTH_USER_MODEL", "accounts.User")


class Application(AuditedModel):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    seeker = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
    )

    cover_note = models.TextField(blank=True)
    proposed_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    applied_at = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.seeker} -> {self.job.title}"

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["job"]),
            models.Index(fields=["seeker"]),
        ]

    def clean(self) -> None:
        """Sanitize and validate fields before saving."""
        super().clean()

        # Sanitize cover note (may be None or expression)
        self.cover_note = sanitize_text_field(cast("str | None", self.cover_note))

        # Validate proposed rate if provided
        if self.proposed_rate is not None:
            # DecimalField may supply a Combinable expression; cast to a simple union
            # acceptable to the validator.
            validate_decimal_range(cast("str | int | float", self.proposed_rate), min_value=None)
