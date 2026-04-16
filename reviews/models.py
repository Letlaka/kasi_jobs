from typing import ClassVar, cast

from applications.models import Application
from django.conf import settings
from django.core.exceptions import ValidationError
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
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["job", "reviewer"], name="unique_review_job_reviewer"
            ),
        ]
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

        # Business rules: only completed jobs may be reviewed; poster cannot
        # review their own job; reviewer must be a seeker with an accepted application.
        job = getattr(self, "job", None)
        reviewer = getattr(self, "reviewer", None)
        if job is not None:
            job_status = getattr(job, "status", None)
            if job_status != Job.JobStatus.COMPLETED:
                raise ValidationError(
                    "Reviews can only be left for completed jobs.", code="job_not_completed"
                )

            poster = getattr(job, "poster", None)
            if poster is not None and poster == reviewer:
                raise ValidationError(
                    "The job poster cannot review their own job.", code="poster_self_review"
                )

            if reviewer is not None:
                # Reviewer must have an accepted application for this job.
                has_accepted = Application.objects.filter(  # type: ignore[attr-defined]
                    job=job,
                    seeker=reviewer,
                    status=Application.ApplicationStatus.ACCEPTED,
                ).exists()
                if not has_accepted:
                    raise ValidationError(
                        "Reviewer must have an accepted application for this job.",
                        code="no_accepted_application",
                    )
