from __future__ import annotations

import logging as _logging
from typing import TYPE_CHECKING

from allauth.account.adapter import DefaultAccountAdapter
from django.core.exceptions import PermissionDenied
from django.utils import timezone

if TYPE_CHECKING:  # pragma: no cover
    from django.http import HttpRequest

from utilities import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Enforces account lockouts and emits structured signup logs.
    """

    def authenticate(
        self,
        request: HttpRequest,
        **credentials: object,
    ) -> object | None:
        user = super().authenticate(request, **credentials)

        # Authentication failed → nothing to enforce here
        if user is None:
            return None

        # Hard lock enforcement (authoritative)
        locked_until = getattr(user, "locked_until", None)
        if locked_until and locked_until > timezone.now():
            raise PermissionDenied("Account temporarily locked due to failed logins")

        return user

    def save_user(
        self, request: HttpRequest, user: object, form: object, *, commit: bool = True
    ) -> object:
        user = super().save_user(request, user, form, commit=commit)
        try:
            logger = get_logger(__name__)
            log_event(
                logger,
                log_name=LogName.SECURITY,
                event_code=EventCode.SECURITY_SIGNUP,
                event="account.signup",
                user=user,
                email=getattr(user, "email", None),
            )
        except Exception as exc:  # pragma: no cover
            _logging.getLogger(__name__).exception(
                "Failed to emit structured signup event: %s", exc
            )
        return user
