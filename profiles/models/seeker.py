from decimal import Decimal
from typing import ClassVar, cast

from django.db import models

from utilities.app_logging import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName
from utilities.validators import sanitize_text_field, validate_decimal_range

from .base import BaseProfile
from .skills import Skill

MAX_TRAVEL_KM = 500

class SeekerProfile(BaseProfile):
    """
    Represents a job seeker profile (e.g. someone seeking work in trades like plumbing or painting).
    """

    skills: models.ManyToManyField = models.ManyToManyField(
        Skill, blank=True, through="SeekerSkill", related_name="seekers"
    )
    hourly_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional hourly rate estimate",
    )

    availability_notes = models.CharField(max_length=255, blank=True)

    has_transport = models.BooleanField(default=False)
    willing_to_travel_km = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Maximum distance the worker is willing to travel from their base location",
    )
    # Optional identity verification field
    # django-stubs reports a typing mismatch for nullable FileField generics;
    # silence this narrow check while keeping the field nullable at runtime.
    id_document: models.FileField | None = models.FileField(
        upload_to="id_verification/",
        null=True,
        blank=True,
    )  # type: ignore[misc]
    id_verified = models.BooleanField(default=False)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["hourly_rate"]),
            # `is_verified` is defined on BaseProfile (abstract) and indexed here intentionally.
            models.Index(fields=["is_verified"]),
        ]

    def __str__(self) -> str:
        username = getattr(self.user, "username", str(self.user))
        return f"{username}'s seeker profile"

    def clean(self) -> None:
        """Sanitize and validate seeker-specific fields."""
        super().clean()

        logger = get_logger(__name__)

        # Sanitize textual fields
        self.availability_notes = sanitize_text_field(
            cast("str | None", self.availability_notes), max_length=255
        )

        # Validate hourly_rate if present
        if self.hourly_rate is not None:
            try:
                validate_decimal_range(
                    cast("str | int | float | Decimal", self.hourly_rate),
                    min_value=Decimal("0"),
                )
            except Exception:
                log_event(
                    logger,
                    log_name=LogName.APPLICATION,
                    event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
                    event="seeker_hourly_rate_invalid",
                    field="hourly_rate",
                )
                raise

        # Validate willing_to_travel_km range (if set)
        if self.willing_to_travel_km is not None:
            try:
                travel = cast("int | float | str", self.willing_to_travel_km)
                if not (0 <= int(travel) <= MAX_TRAVEL_KM):
                    raise ValueError("willing_to_travel_km out of range")
            except Exception:
                log_event(
                    logger,
                    log_name=LogName.APPLICATION,
                    event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
                    event="seeker_travel_km_invalid",
                    field="willing_to_travel_km",
                )
                raise
