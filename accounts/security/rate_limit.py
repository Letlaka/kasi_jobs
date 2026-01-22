from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from config.settings.env import env
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from utilities import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName

logger = get_logger(__name__)


RATE_LIMIT_MAX_ATTEMPTS = env.int("ACCOUNTS_LOGIN_MAX_ATTEMPTS")
RATE_LIMIT_WINDOW = env.int("ACCOUNTS_LOGIN_WINDOW_SECONDS")
RATE_LIMIT_LOCKOUT = env.int("ACCOUNTS_LOCKOUT_SECONDS")


def get_client_ip(request: object | None) -> str | None:
    if request is None:
        return None

    meta = getattr(request, "META", None)
    if not isinstance(meta, Mapping):
        return None

    xff = meta.get("HTTP_X_FORWARDED_FOR")
    if isinstance(xff, str) and xff:
        return xff.split(",")[0].strip()

    remote = meta.get("REMOTE_ADDR")
    return remote if isinstance(remote, str) else None


def increment_cache_counter(key: str | None) -> int:
    if not key:
        return 0

    try:
        if hasattr(cache, "incr"):
            try:
                return cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=RATE_LIMIT_WINDOW)
                return 1

        value = int(cache.get(key) or 0) + 1
        cache.set(key, value, timeout=RATE_LIMIT_WINDOW)
        return value
    except (TypeError, ValueError):
        return 0


def rate_limit_and_maybe_lock(
    *,
    credentials: Mapping[str, object] | None,
    request: object | None,
) -> None:
    """
    Hybrid rate-limiter:
    - Cache for throttling
    - User.locked_until for authoritative lock
    """
    username: str | None = None
    if isinstance(credentials, Mapping):
        raw = credentials.get("username") or credentials.get("email")
        username = raw if isinstance(raw, str) else None

    ip = get_client_ip(request)
    user_model = get_user_model()

    user: Any | None = None
    if username:
        user = user_model.objects.filter(username=username).first()
        if user is None and "@" in username:
            user = user_model.objects.filter(email=username).first()

    if user is not None:
        user_key = f"accounts:login:fail:user:{user.pk}"
        lock_key = f"accounts:login:lock:user:{user.pk}"
    else:
        uname_hash = hashlib.sha256((username or "").encode()).hexdigest()[:16]
        user_key = f"accounts:login:fail:username:{uname_hash}"
        lock_key = f"accounts:login:lock:username:{uname_hash}"

    ip_key = f"accounts:login:fail:ip:{ip}" if ip else None

    if cache.get(lock_key):
        return

    user_failures = increment_cache_counter(user_key)
    ip_failures = increment_cache_counter(ip_key)

    ip_threshold = max(1, RATE_LIMIT_MAX_ATTEMPTS * 2)

    if user is None:
        return

    if user_failures < RATE_LIMIT_MAX_ATTEMPTS and ip_failures < ip_threshold:
        return

    lock_until = timezone.now() + timedelta(seconds=RATE_LIMIT_LOCKOUT)

    try:
        user.locked_until = lock_until
        user.save(update_fields=["locked_until"])
    except (AttributeError, ValueError):
        logging.getLogger(__name__).exception("Failed to persist locked_until for user %s", user.pk)

    cache.set(lock_key, 1, timeout=RATE_LIMIT_LOCKOUT)
    cache.set(user_key, 0, timeout=RATE_LIMIT_WINDOW)

    log_event(
        logger,
        log_name=LogName.SECURITY,
        event_code=EventCode.SECURITY_ACCOUNT_LOCKED,
        event="account.locked",
        user=user,
        object_pk=str(user.pk),
        locked_until=lock_until.isoformat(),
    )
