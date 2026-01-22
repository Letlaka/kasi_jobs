from typing import ClassVar, cast

from django.db import models

from utilities.app_logging import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName
from utilities.validators import sanitize_text_field

from .base import BaseProfile


class PosterProfile(BaseProfile):
    """
    Represents a person or small business posting jobs.
    """

    organization_name = models.CharField(max_length=128, blank=True)
    is_business = models.BooleanField(default=False)

    default_location = models.CharField(
        max_length=255,
        help_text="Typical job location",
        blank=True,
    )

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["is_business"]),
        ]

    def __str__(self) -> str:
        org = str(self.organization_name)
        user_display = getattr(self.user, "username", str(self.user))
        return org or f"{user_display}'s poster profile"

    def clean(self) -> None:
        """Sanitize poster-specific textual fields."""
        super().clean()

        logger = get_logger(__name__)

        try:
            self.organization_name = sanitize_text_field(
                cast("str | None", self.organization_name), max_length=128
            )
            self.default_location = sanitize_text_field(
                cast("str | None", self.default_location), max_length=255
            )
        except Exception:
            log_event(
                logger,
                log_name=LogName.APPLICATION,
                event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
                event="poster_sanitization_failed",
                field="organization_name|default_location",
            )
            raise
