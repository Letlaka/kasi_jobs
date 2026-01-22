from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.db import DatabaseError
from django.shortcuts import render
from django.utils import timezone

from utilities import get_logger

from .models import User

logger = get_logger(__name__)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from django.http import HttpRequest, HttpResponse

AccessAttempt: type[Any] | None
try:
    from axes.models import AccessAttempt as _AccessAttempt

    AccessAttempt = _AccessAttempt
except (ImportError, ModuleNotFoundError):
    AccessAttempt = None


def _lookup_user_by_pk(q: str) -> User | None:
    try:
        return User.objects.filter(pk=int(q)).first()
    except ValueError:
        logger.exception("Failed to lookup user by pk")
        return None


def _lookup_user_by_username(q: str) -> User | None:
    try:
        return User.objects.filter(username=q).first()
    except Exception:
        logger.exception("Failed to lookup user by username")
        return None


def _get_ip_info(q: str) -> dict[str, Any]:
    ip_key = f"accounts:login:fail:ip:{q}"
    lock_key = f"accounts:login:lock:ip:{q}"
    return {
        "ip": q,
        "failures": cache.get(ip_key) or 0,
        "failures_ttl": cache.ttl(ip_key) if hasattr(cache, "ttl") else None,  # pyright: ignore[reportAttributeAccessIssue]
        "lock_marker": cache.get(lock_key),
        "lock_ttl": cache.ttl(lock_key) if hasattr(cache, "ttl") else None,  # pyright: ignore[reportAttributeAccessIssue]
    }


def _collect_username_info(q: str) -> dict[str, Any] | None:
    uname_hash = hashlib.sha256(q.encode()).hexdigest()[:16]
    uname_fail_key = f"accounts:login:fail:username:{uname_hash}"
    uname_lock_key = f"accounts:login:lock:username:{uname_hash}"
    return {
        "username": q,
        "meta": cache.get(f"accounts:login:meta:username:{uname_hash}"),
        "failures": cache.get(uname_fail_key) or 0,
        "failures_ttl": cache.ttl(uname_fail_key) if hasattr(cache, "ttl") else None,  # pyright: ignore[reportAttributeAccessIssue]
        "lock_marker": cache.get(uname_lock_key),
        "lock_ttl": cache.ttl(uname_lock_key) if hasattr(cache, "ttl") else None,  # pyright: ignore[reportAttributeAccessIssue]
    }


def _collect_axes_entries(q: str | None, ip: str | None) -> tuple[Any, Any, list[str]]:
    axes_attempts = None
    axes_recent = None
    ip_related: list[str] = []
    if AccessAttempt is None:
        return axes_attempts, axes_recent, ip_related

    try:
        if q:
            axes_attempts = AccessAttempt.objects.filter(username__icontains=q)[:25]
        else:
            axes_attempts = AccessAttempt.objects.all()[:25]
    except DatabaseError:
        axes_attempts = None

    try:
        axes_recent = AccessAttempt.objects.all().order_by("-attempt_time")[:25]
    except DatabaseError:
        axes_recent = None

    if ip:
        try:
            ip_related = list(
                AccessAttempt.objects.filter(ip_address=ip)
                .exclude(username__isnull=True)
                .values_list("username", flat=True)
                .distinct()
            )
        except DatabaseError:
            ip_related = []

    return axes_attempts, axes_recent, ip_related


@admin.site.admin_view
@staff_member_required
def rate_limit_dashboard(request: HttpRequest) -> HttpResponse:
    """Admin view to inspect rate-limit counters and locks.

    Query params:
    - q: user id, username, or ip
    """
    q = request.GET.get("q", "").strip()
    context: dict[str, Any] = {"query": q, "now": timezone.now(), "results": []}

    def _get_user_info(user: User) -> dict[str, Any]:
        pk = str(user.pk)
        user_key = f"accounts:login:fail:user:{pk}"
        lock_key = f"accounts:login:lock:user:{pk}"
        meta_key = f"accounts:login:meta:user:{pk}"
        return {
            "user": user,
            "meta": cache.get(meta_key),
            "failures": cache.get(user_key) or 0,
            "failures_ttl": cache.ttl(user_key) if hasattr(cache, "ttl") else None,  # pyright: ignore[reportAttributeAccessIssue]
            "lock_marker": cache.get(lock_key),
            "lock_ttl": cache.ttl(lock_key) if hasattr(cache, "ttl") else None,  # pyright: ignore[reportAttributeAccessIssue]
        }

    # Try interpret q as a numeric pk
    if q.isdigit():
        user = _lookup_user_by_pk(q)
        if user:
            context["results"].append(_get_user_info(user))

    # Try username lookup
    if not context["results"] and q:
        user = _lookup_user_by_username(q)
        if user:
            context["results"].append(_get_user_info(user))
    # expose username-info regardless (useful when there's no user record)
    if q:
        context["username_info"] = _collect_username_info(q)

    # If q looks like an IP address, show ip counter
    if q and (q.count(".") >= 1 or ":" in q):
        context["ip"] = _get_ip_info(q)
        # include failure meta for ip
        context["ip_meta"] = cache.get(f"accounts:login:meta:ip:{q}")

    # collect axes entries and ip->username mapping
    axes_attempts, axes_recent, ip_related = _collect_axes_entries(q, q)
    context["axes_attempts"] = axes_attempts
    context["axes_recent_attempts"] = axes_recent
    context["ip_related_usernames"] = ip_related

    return render(request, "admin/accounts/rate_limits.html", context)
