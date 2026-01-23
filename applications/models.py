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

    class ApplicationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    # canonical state for the application lifecycle. Replace boolean flags
    # with this explicit enum to avoid invalid state combinations.
    status = models.CharField(
        max_length=32, choices=ApplicationStatus.choices, default=ApplicationStatus.PENDING
    )

    def __str__(self) -> str:
        return f"{self.seeker} -> {self.job.title}"

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["job"]),
            models.Index(fields=["seeker"]),
            models.Index(fields=["status"]),
            models.Index(fields=["applied_at"]),
            # composite indexes to support queries like
            # WHERE job_id = X ORDER BY applied_at DESC
            models.Index(fields=["job", "applied_at"], name="apps_job_applied_at_idx"),
            # WHERE seeker_id = X ORDER BY applied_at DESC
            models.Index(fields=["seeker", "applied_at"], name="apps_seeker_applied_at_idx"),
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


ACTION_ACCEPT = "accept"
ACTION_REJECT = "reject"


class ApplicationAction(AuditedModel):
    """Persistent audit record for application state transitions and actions.

    Stored separately from the Application model to provide an immutable event
    stream of actions taken on an application (accept, reject, etc.).
    """

    ACTION_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (ACTION_ACCEPT, "accepted"),
        (ACTION_REJECT, "rejected"),
    ]

    application = models.ForeignKey(
        "applications.Application",
        on_delete=models.CASCADE,
        related_name="actions",
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="application_actions"
    )
    metadata = models.JSONField(null=True, blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["application"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return (
            f"{self.action} @ {self.performed_at} on {getattr(self, 'application_id', 'unknown')}"
        )
