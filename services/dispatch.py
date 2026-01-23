"""Background dispatch helper.

Provides a small, framework-agnostic hook to schedule side-effects after a
successful DB transaction commit. Consumers can connect to
`background_task_requested` and forward the event to Celery, webhooks,
or other systems. This keeps service functions pure and non-blocking.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.dispatch import Signal

from utilities.app_logging.helpers import get_logger

logger = get_logger(__name__)

# Signal(name=str, payload=dict)  # noqa: ERA001
background_task_requested = Signal()


def count_background_receivers() -> int:
    """Return the number of receivers currently connected to the
    `background_task_requested` signal.

    Note: `Signal.receivers` is an internal API but stable in Django's
    implementation; we use it here for a lightweight health check.
    """
    try:
        return len(background_task_requested.receivers)
    except (AttributeError, TypeError):
        # Be conservative: if introspection fails, report zero receivers.
        return 0


def emit_background_task(name: str, payload: dict[str, Any]) -> None:
    """Schedule a background task emission after the current transaction commits.

    This does not perform work itself; it sends `background_task_requested`
    on commit. Receivers should be responsible for enqueuing/processing.
    """

    def _send() -> None:
        try:
            background_task_requested.send(sender=emit_background_task, name=name, payload=payload)
        except (RuntimeError, ValueError, TypeError) as exc:
            # Background task emission is non-critical; downgrade to warning
            # to avoid noisy exception traces for transient or receiver errors.
            logger.warning("failed to emit background task signal: %s", exc)

    transaction_management_error = getattr(transaction, "TransactionManagementError", None)
    try:
        transaction.on_commit(_send)
    except Exception as exc:
        # If transaction machinery not available (e.g., tests) or transaction
        # management not available, attempt immediate send. Downgrade logging to
        # warning to avoid noisy traces for optional side-effects.
        if isinstance(exc, AttributeError) or (
            transaction_management_error is not None
            and isinstance(exc, transaction_management_error)
        ):
            try:
                _send()
            except (RuntimeError, ValueError, TypeError) as exc:
                logger.warning("failed to send background task immediately: %s", exc)
        else:
            raise
