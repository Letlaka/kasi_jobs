from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from utilities import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName

logger = get_logger(__name__)
User = get_user_model()

hist_model = getattr(getattr(User, "history", None), "model", None)

if hist_model is not None:

    @receiver(post_save, sender=hist_model)
    def handle_user_history_created(
        sender: object,  # noqa: ARG001
        instance: object,
        *,
        created: bool,
        **_kwargs: object,
    ) -> None:
        if not created:
            return

        try:
            history_user: Any | None = getattr(instance, "history_user", None)
            history_type = getattr(instance, "history_type", None)
            object_pk = str(getattr(instance, "id", getattr(instance, "pk", "")))

            payload: dict[str, Any] = {
                "history_type": history_type,
            }

            # Detect locked_until changes from historical record
            old_locked_until = getattr(instance, "prev_record", None)
            new_locked_until = getattr(instance, "locked_until", None)

            if old_locked_until is not None:
                old_val = getattr(old_locked_until, "locked_until", None)
            else:
                old_val = None

            if old_val != new_locked_until:
                now = timezone.now()
                if new_locked_until and new_locked_until > now:
                    payload["event"] = "account.locked"
                    payload["locked_until"] = new_locked_until.isoformat()
                    event_code = EventCode.SECURITY_ACCOUNT_LOCKED
                else:
                    payload["event"] = "account.unlocked"
                    payload["locked_until"] = None
                    event_code = EventCode.SECURITY_ACCOUNT_UNLOCKED
            else:
                payload["event"] = "accounts.user.history.created"
                event_code = EventCode.AUDIT_EXPORT_STARTED

            with contextlib.suppress(RuntimeError):
                log_event(
                    logger,
                    log_name=LogName.AUDIT,
                    event_code=event_code,
                    event=payload.pop("event"),
                    user=history_user,
                    model="accounts.User",
                    object_pk=object_pk,
                    **payload,
                )

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to emit audit log from simple-history record: %s", exc)


with contextlib.suppress(ImportError):
    from auditlog.models import LogEntry

    @receiver(post_save, sender=LogEntry)
    def handle_auditlog_entry(
        sender: object,  # noqa: ARG001
        instance: object,
        *,
        created: bool,
        **_kwargs: object,
    ) -> None:
        if not created:
            return

        try:
            ct = getattr(instance, "content_type", None)
            if not ct or ct.app_label != "accounts":
                return

            changes = getattr(instance, "changes", None) or {}
            object_pk = str(getattr(instance, "object_pk", ""))

            # Detect locked_until change via auditlog payload
            if isinstance(changes, dict) and "locked_until" in changes:
                _old_val, new_val = changes.get("locked_until", (None, None))

                now = timezone.now()
                if new_val and isinstance(new_val, datetime) and new_val > now:
                    event = "account.locked"
                    event_code = EventCode.SECURITY_ACCOUNT_LOCKED
                    extra = {"locked_until": new_val.isoformat()}
                else:
                    event = "account.unlocked"
                    event_code = EventCode.SECURITY_ACCOUNT_UNLOCKED
                    extra = {}
            else:
                event = "accounts.user.auditlog.entry"
                event_code = EventCode.AUDIT_EXPORT_STARTED
                extra = {"changes": changes}

            actor_user: Any | None = getattr(instance, "actor", None) or getattr(
                instance, "actor_object_id", None
            )

            with contextlib.suppress(RuntimeError):
                log_event(
                    logger,
                    log_name=LogName.AUDIT,
                    event_code=event_code,
                    event=event,
                    user=actor_user,
                    model="accounts.User",
                    object_pk=object_pk,
                    **extra,
                )

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Auditlog receiver failed: %s", exc)
