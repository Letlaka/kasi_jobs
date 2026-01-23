"""Helpers for workflow action handlers.

Provide a small mixin to standardize workflow actions (accept/reject/etc.).
Callers can use `WorkflowActionMixin.enforce_contract()` at the start of an
action to make intentions obvious and to centralize future checks.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpRequest


class WorkflowActionMixin:
    """Mixin providing small helpers for workflow actions.

    Usage:
        class MyViewSet(WorkflowActionMixin, viewsets.ModelViewSet):
            @action(...)
            def accept(self, request, pk=None):
                self.enforce_contract(request)
                ...

    `enforce_contract` is intentionally lightweight: it documents the required
    checks and can be extended to perform static validation or runtime
    assertions (e.g., ensure throttles are present, metrics hooks wired).
    """

    def enforce_contract(self, request: HttpRequest, *, require_throttle: bool = True) -> None:
        """Enforce the developer-facing workflow contract for actions.

        - `require_throttle` when True indicates the action should apply a
          per-action throttle scope (view should set `self.throttle_scope`).

        This method is a noop at runtime but serves as a single place to add
        runtime assertions or instrumentation in the future.
        """
        # Intentionally minimal for now; can be extended to raise or log
        # when contracts are violated. Emit a warning when the view hasn't
        # set a per-action `throttle_scope` while `require_throttle` is True.
        logger = logging.getLogger(__name__)
        _ = request
        if require_throttle:
            throttle = getattr(self, "throttle_scope", None)
            if not throttle:
                # In production we log an error to make missing throttles visible;
                # in non-production environments we warn to avoid noisy failures.
                env = getattr(settings, "ENVIRONMENT", None) or getattr(settings, "ENV", "local")
                msg = (
                    "WorkflowActionMixin: missing throttle_scope for action=%s; "
                    "set `self.throttle_scope` before calling service"
                )
                if env == "production":
                    logger.error(msg, getattr(self, "action", None))
                else:
                    logger.warning(msg, getattr(self, "action", None))
