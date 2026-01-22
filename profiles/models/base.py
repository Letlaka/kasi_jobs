from typing import cast

from django.conf import settings
from django.db import models

from utilities.app_logging import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName
from utilities.models import AuditedModel
from utilities.validators import sanitize_text_field

# Expose AUTH_USER_MODEL safely for type checking
AUTH_USER_MODEL: str = getattr(settings, "AUTH_USER_MODEL", "accounts.User")


class BaseProfile(AuditedModel):
    user = models.OneToOneField(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(class)s",
    )

    is_verified = models.BooleanField(default=False)
    bio = models.TextField(blank=True)

    class Meta:
        abstract = True

    def clean(self) -> None:
        """Sanitize common profile fields before saving."""
        super().clean()

        logger = get_logger(__name__)

        try:
            self.bio = sanitize_text_field(cast("str | None", self.bio))
        except Exception:
            log_event(
                logger,
                log_name=LogName.APPLICATION,
                event_code=EventCode.AUDIT_VALIDATION_DECIMAL_FAILED,
                event="profile_bio_sanitization_failed",
                field="bio",
            )
            raise
