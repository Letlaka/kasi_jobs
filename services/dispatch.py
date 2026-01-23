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

# Minimum tuple length for a (key, receiver) entry in Signal.receivers
MIN_TUPLE_LEN = 2

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


def emit_background_task(name: str, payload: dict[str, Any]) -> None:  # noqa: C901
    """Schedule a background task emission after the current transaction commits.

    This does not perform work itself; it sends `background_task_requested`
    on commit. Receivers should be responsible for enqueuing/processing.
    """

    def _send() -> None:  # noqa: C901
        # Manually invoke live receivers so we can support both receiver
        # signatures that expect a positional `_sender` argument and those
        # that expect `sender=` as a keyword. We prefer calling each
        # receiver once using the form that binds correctly.
        # Use the public `receivers` attribute and resolve callable objects
        # to support different Django internal representations while keeping
        # mypy happy (avoids private _live_receivers attribute).
        receivers_raw = getattr(background_task_requested, "receivers", [])
        resolved_receivers: list[object] = []
        for entry in receivers_raw:
            # entry may be a (key, receiver) tuple or a direct receiver
            receiver_obj = (
                entry[1] if isinstance(entry, tuple) and len(entry) >= MIN_TUPLE_LEN else entry
            )

            if isinstance(receiver_obj, (list, tuple)):
                resolved_receivers.extend(list(receiver_obj))
            else:
                resolved_receivers.append(receiver_obj)

        for r in resolved_receivers:
            # Accept several receiver shapes: callable, or iterable containing
            # a callable (some internal representations use lists).
            candidates = [r]
            if isinstance(r, (list, tuple)):
                candidates = list(r)

            called = False
            for candidate in candidates:
                if not callable(candidate):
                    continue
                try:
                    candidate(emit_background_task, name=name, payload=payload)
                    called = True
                    break
                except TypeError:
                    try:
                        candidate(sender=emit_background_task, name=name, payload=payload)
                        called = True
                        break
                    except Exception as exc:  # noqa: BLE001 - receiver failures are non-critical
                        logger.warning("failed to emit background task signal: %s", exc)
                except Exception as exc:  # noqa: BLE001 - receiver failures are non-critical
                    logger.warning("failed to emit background task signal: %s", exc)
            if not called:
                logger.debug("no callable receiver found for background_task_requested")

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
