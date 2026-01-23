from django.apps import AppConfig
from django.conf import settings
from services.dispatch import count_background_receivers

from utilities.app_logging.helpers import get_logger


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core"

    def ready(self) -> None:  # pragma: no cover - environment-specific startup check
        """Perform lightweight startup checks.

        In production, warn loudly (error-level) if no background task receivers
        are registered. This helps catch misconfigurations where side-effect
        processing (emails, notifications) would silently no-op.
        """
        env = getattr(settings, "ENVIRONMENT", None) or getattr(settings, "ENV", "local")
        logger = get_logger(__name__)
        try:
            if env == "production":
                receivers = count_background_receivers()
                if receivers == 0:
                    logger.error(
                        "no background task receivers registered at startup; "
                        "expected Celery worker or webhook bridge",
                    )
                else:
                    logger.info("background task receivers registered: %d", receivers)
        except Exception as exc:
            logger.exception("failed to introspect background task receivers: %s", exc)
