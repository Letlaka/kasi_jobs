from decimal import Decimal
from typing import ClassVar, cast

from django.conf import settings
from django.db import models
from profiles.models.skills import Skill

from utilities.app_logging import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName
from utilities.models import AuditedModel
from utilities.validators import sanitize_text_field, validate_decimal_range

# Resolve mypy complaint about settings attributes
AUTH_USER_MODEL: str = getattr(settings, "AUTH_USER_MODEL", "accounts.User")
MAX_ESTIMATED_HOURS = 10000


class Job(AuditedModel):
    poster = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posted_jobs",
    )

    title = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    skills_needed: models.ManyToManyField = models.ManyToManyField(Skill, blank=True)

    estimated_hours = models.PositiveSmallIntegerField()
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2)

    posted_at = models.DateTimeField(auto_now_add=True)

    # Replace boolean `is_active` with explicit lifecycle `status` to enforce
    # job lifecycle transitions and avoid invalid combinations.
    class JobStatus(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    status = models.CharField(max_length=32, choices=JobStatus.choices, default=JobStatus.OPEN)

    def __str__(self) -> str:
        return str(self.title)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["poster"]),
            models.Index(fields=["posted_at"]),
            models.Index(fields=["status"]),
            # composite index to support queries filtering by status and
            # ordering by posted_at (e.g. ?status=open)
            models.Index(fields=["status", "posted_at"], name="jobs_status_posted_at_idx"),
        ]

    def clean(self) -> None:
        """Sanitize and validate job fields before saving."""
        super().clean()

        logger = get_logger(__name__)

        # Sanitize textual fields
        self.title = sanitize_text_field(cast("str | None", self.title), max_length=255)
        self.description = sanitize_text_field(cast("str | None", self.description))
        self.location = sanitize_text_field(cast("str | None", self.location), max_length=255)

        # Validate numeric fields
        try:
            # Cast to a simple numeric/string union for validator compatibility
            validate_decimal_range(
                cast("str | int | float | Decimal", self.hourly_rate),
                min_value=Decimal("0"),
            )
        except Exception:
            log_event(
                logger,
                log_name=LogName.APPLICATION,
                event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
                event="hourly_rate_invalid",
                field="hourly_rate",
            )
            raise

        # estimated_hours can be a Combinable expression; cast to int-compatible type
        estimated = cast("int | float | str", self.estimated_hours)
        if not (0 < int(estimated) <= MAX_ESTIMATED_HOURS):
            log_event(
                logger,
                log_name=LogName.APPLICATION,
                event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
                event="estimated_hours_out_of_range",
                field="estimated_hours",
            )
            raise ValueError("estimated_hours out of acceptable range")
