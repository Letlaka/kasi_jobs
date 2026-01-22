from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, cast

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from utilities import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser as UserType

logger = get_logger(__name__)
User = get_user_model()

TRACK_FIELDS = ("email", "first_name", "last_name", "phone")


@receiver(pre_save, sender=User)
def user_pre_save(sender: object, instance: UserType, **_kwargs: object) -> None:  # noqa: ARG001
    """
    Capture a snapshot of selected user fields before save so we can
    emit precise post-save change events.
    """
    try:
        if not instance.pk:
            cast("Any", instance)._pre_save_snapshot = None
            return

        orig = (
            User.objects.filter(pk=instance.pk)
            .only(*TRACK_FIELDS, "password", "locked_until")
            .first()
        )
        if not orig:
            cast("Any", instance)._pre_save_snapshot = None
            return

        cast("Any", instance)._pre_save_snapshot = {
            f: getattr(orig, f, None) for f in TRACK_FIELDS
        } | {
            "password": orig.password,
            "locked_until": getattr(orig, "locked_until", None),
        }

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Pre-save snapshot failed: %s", exc)


@receiver(post_save, sender=User)
def user_post_save(
    sender: object,  # noqa: ARG001
    instance: UserType,
    *,
    created: bool,
    **_kwargs: object,
) -> None:
    """
    Emit security/profile events based on changes detected between
    pre-save snapshot and the saved instance.
    """
    if created:
        return

    snapshot = getattr(instance, "_pre_save_snapshot", None)
    if not snapshot:
        return

    try:
        pk = str(instance.pk)

        # --------------------------------------------------------------
        # Password change detection
        # --------------------------------------------------------------
        if snapshot.get("password") != instance.password:
            with contextlib.suppress(RuntimeError):
                log_event(
                    logger,
                    log_name=LogName.SECURITY,
                    event_code=EventCode.SECURITY_PASSWORD_CHANGED,
                    event="account.password.changed",
                    user=instance,
                    object_pk=pk,
                )

        # --------------------------------------------------------------
        # Account lock / unlock detection via locked_until
        # --------------------------------------------------------------
        old_locked_until = snapshot.get("locked_until")
        new_locked_until = getattr(instance, "locked_until", None)
        now = timezone.now()

        if old_locked_until != new_locked_until:
            if new_locked_until and new_locked_until > now:
                with contextlib.suppress(RuntimeError):
                    log_event(
                        logger,
                        log_name=LogName.SECURITY,
                        event_code=EventCode.SECURITY_ACCOUNT_LOCKED,
                        event="account.locked",
                        user=instance,
                        object_pk=pk,
                        locked_until=new_locked_until.isoformat(),
                    )
            else:
                with contextlib.suppress(RuntimeError):
                    log_event(
                        logger,
                        log_name=LogName.SECURITY,
                        event_code=EventCode.SECURITY_ACCOUNT_UNLOCKED,
                        event="account.unlocked",
                        user=instance,
                        object_pk=pk,
                    )

        # --------------------------------------------------------------
        # Profile / account detail changes
        # --------------------------------------------------------------
        changes = {
            field: {"old": snapshot.get(field), "new": getattr(instance, field, None)}
            for field in TRACK_FIELDS
            if snapshot.get(field) != getattr(instance, field, None)
        }

        if changes:
            with contextlib.suppress(RuntimeError):
                log_event(
                    logger,
                    log_name=LogName.SECURITY,
                    event_code=EventCode.SECURITY_ACCOUNT_UPDATED,
                    event="account.details.changed",
                    user=instance,
                    object_pk=pk,
                    changes=changes,
                )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("User post-save processing failed: %s", exc)
