from __future__ import annotations

import contextlib
import hashlib
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.core.cache import cache
from django.dispatch import receiver
from django.utils import timezone

from accounts.security.rate_limit import RATE_LIMIT_WINDOW, get_client_ip, rate_limit_and_maybe_lock
from utilities import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName

try:
    from allauth.account.signals import user_signed_up
except ImportError:  # pragma: no cover
    user_signed_up = None

logger = get_logger(__name__)

LOGIN_SUCCESS_COUNTER: Any | None = None
LOGIN_FAILURE_COUNTER: Any | None = None
SIGNUP_COUNTER: Any | None = None

try:
    from prometheus_client import Counter

    _ENV = getattr(settings, "ENVIRONMENT", None) or getattr(settings, "ENV", "local")
    LOGIN_SUCCESS_COUNTER = Counter(
        "accounts_login_success_total", "Total successful logins", ["env"]
    ).labels(_ENV)
    LOGIN_FAILURE_COUNTER = Counter(
        "accounts_login_failure_total", "Total failed logins", ["env"]
    ).labels(_ENV)
    SIGNUP_COUNTER = Counter("accounts_signup_total", "Total signups", ["env"]).labels(_ENV)
except (ImportError, RuntimeError):
    LOGIN_SUCCESS_COUNTER = LOGIN_FAILURE_COUNTER = SIGNUP_COUNTER = None


@receiver(user_logged_in)
def handle_user_logged_in(**kwargs: object) -> None:
    user: Any | None = kwargs.get("user")
    request = kwargs.get("request")

    if LOGIN_SUCCESS_COUNTER:
        with contextlib.suppress(RuntimeError):
            LOGIN_SUCCESS_COUNTER.inc()

    # Optional: clear cache soft-lock on success
    if user is not None:
        with contextlib.suppress(RuntimeError):
            cache.delete(f"accounts:login:lock:user:{user.pk}")
            cache.delete(f"accounts:login:fail:user:{user.pk}")

    with contextlib.suppress(RuntimeError):
        log_event(
            logger,
            log_name=LogName.SECURITY,
            event_code=EventCode.SECURITY_LOGIN_SUCCESS,
            event="auth.login",
            user=user,
            username=getattr(user, "username", None),
            request=request,
        )


@receiver(user_logged_out)
def handle_user_logged_out(**kwargs: object) -> None:
    user: Any | None = kwargs.get("user")
    request = kwargs.get("request")

    with contextlib.suppress(RuntimeError):
        log_event(
            logger,
            log_name=LogName.SECURITY,
            event_code=EventCode.SECURITY_LOGOUT,
            event="auth.logout",
            user=user,
            username=getattr(user, "username", None),
            request=request,
        )


@receiver(user_login_failed)
def handle_user_login_failed(credentials: dict, request: object | None = None) -> None:
    if LOGIN_FAILURE_COUNTER:
        with contextlib.suppress(RuntimeError):
            LOGIN_FAILURE_COUNTER.inc()

    rate_limit_and_maybe_lock(credentials=credentials, request=request)

    # Record lightweight failure metadata for admin inspection
    try:
        ts = timezone.now().isoformat()
        ip = get_client_ip(request)
        username = credentials.get("username")
        meta = {"last_failure_at": ts, "last_failure_ip": ip, "reason": "invalid_credentials"}

        timeout = RATE_LIMIT_WINDOW if isinstance(RATE_LIMIT_WINDOW, int) else 300

        # store by username-hash
        if isinstance(username, str):
            h = hashlib.sha256(username.encode()).hexdigest()[:16]
            cache.set(f"accounts:login:meta:username:{h}", meta, timeout=timeout)

        # store by ip
        if ip:
            cache.set(f"accounts:login:meta:ip:{ip}", meta, timeout=timeout)

        # if a matching user exists, store by user pk as well
        try:
            user_model = get_user_model()
            user = None
            if isinstance(username, str):
                user = user_model.objects.filter(username=username).first()
                if user is None and "@" in username:
                    user = user_model.objects.filter(email=username).first()
            if user is not None:
                cache.set(f"accounts:login:meta:user:{user.pk}", meta, timeout=timeout)
        except Exception:
            logger.exception("Failed to lookup user for failure metadata")
    except Exception:
        logger.exception("Failed to write login failure metadata")
    with contextlib.suppress(RuntimeError):
        log_event(
            logger,
            log_name=LogName.SECURITY,
            event_code=EventCode.SECURITY_LOGIN_FAILED,
            event="auth.login.failed",
            username=credentials.get("username"),
            request=request,
        )


if user_signed_up is not None:

    @receiver(user_signed_up)
    def handle_user_signed_up(**kwargs: object) -> None:
        user: Any | None = kwargs.get("user")

        if SIGNUP_COUNTER:
            with contextlib.suppress(RuntimeError):
                SIGNUP_COUNTER.inc()

        with contextlib.suppress(RuntimeError):
            log_event(
                logger,
                log_name=LogName.SECURITY,
                event_code=EventCode.SECURITY_SIGNUP,
                event="auth.signed_up",
                user=user,
                username=getattr(user, "username", None),
                email=getattr(user, "email", None),
            )
