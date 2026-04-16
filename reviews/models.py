from typing import ClassVar, cast

from django.conf import settings
from django.db import models
from jobs.models import Job

from utilities.app_logging import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName
from utilities.models import AuditedModel
from utilities.validators import sanitize_text_field

# Expose AUTH_USER_MODEL safely for type checkers
AUTH_USER_MODEL: str = getattr(settings, "AUTH_USER_MODEL", "accounts.User")

# Maximum allowed rating value
MAX_RATING = 5

logger = get_logger(__name__)


class Review(AuditedModel):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("job", "reviewer")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["job"]),
            models.Index(fields=["reviewer"]),
        ]

    def clean(self) -> None:
        """Sanitize and validate review fields before saving."""
        super().clean()

        # Sanitize comment
        try:
            self.comment = sanitize_text_field(cast("str | None", self.comment))
        except Exception:
            log_event(
                logger,
                log_name=LogName.APPLICATION,
                event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
                event="review_comment_sanitization_failed",
                field="comment",
            )
            raise

        # Validate rating is within 1-5
        try:
            rating_val = int(cast("int | str", self.rating))
            if not (1 <= rating_val <= MAX_RATING):
                raise ValueError("rating out of range")
        except Exception:
            log_event(
                logger,
                log_name=LogName.APPLICATION,
                event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
                event="review_rating_invalid",
                field="rating",
            )
            raise
