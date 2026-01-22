from __future__ import annotations

import contextlib
import hashlib
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import path, reverse
from django.urls.exceptions import NoReverseMatch
from django.utils import timezone
from django.utils.html import format_html

from utilities import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName

from .models import User

AccessAttempt: type[Any] | None
try:
    from axes.models import AccessAttempt as _AccessAttempt

    AccessAttempt = _AccessAttempt
except (ImportError, ModuleNotFoundError):
    AccessAttempt = None

logger = get_logger(__name__)

if TYPE_CHECKING:  # pragma: no cover - typing-only imports
    from django.db.models import QuerySet
    from django.http import HttpRequest


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email", "phone")}),
        (
            "Security",
            {"fields": ("locked_until",)},
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_locked",
        "rate_limits_link",
    )

    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    @admin.display(boolean=True, description="Locked")
    def is_locked(self, obj: User) -> bool:
        lu = getattr(obj, "locked_until", None)
        if not isinstance(lu, datetime):
            return False
        return lu > timezone.now()

    actions: tuple[str, ...] = ("lock_users", "unlock_users")

    @admin.action(description="Clear cache lock markers for selected users")
    def clear_cache_locks(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        self._ensure_action_permission(request)
        deleted = 0
        for user in queryset:
            try:
                pk = getattr(user, "pk", None)
                if pk is None:
                    continue
                cache.delete(f"accounts:login:lock:user:{pk}")
                cache.delete(f"accounts:login:fail:user:{pk}")
                username = getattr(user, "username", None)
                if isinstance(username, str):
                    h = hashlib.sha256(username.encode()).hexdigest()[:16]
                    cache.delete(f"accounts:login:lock:username:{h}")
                    cache.delete(f"accounts:login:fail:username:{h}")
                deleted += 1
            except Exception:
                logger.exception(
                    "Failed to clear cache locks for user %s", getattr(user, "pk", None)
                )
        self.message_user(request, f"Cleared cache locks for {deleted} user(s)")

    @admin.action(description="Delete django-axes attempts for selected users")
    def clear_axes_attempts(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        self._ensure_action_permission(request)
        if AccessAttempt is None:
            self.message_user(request, "django-axes not installed; nothing to clear")
            return
        total_deleted = 0
        for user in queryset:
            try:
                username = getattr(user, "username", None)
                if username:
                    qs = AccessAttempt.objects.filter(username=username)
                    # also remove attempts with this user's ip addresses
                    ips = list(qs.values_list("ip_address", flat=True).distinct())
                    if ips:
                        ip_qs = AccessAttempt.objects.filter(ip_address__in=ips)
                        total_deleted += ip_qs.count()
                        ip_qs.delete()
                    total_deleted += qs.count()
                    qs.delete()
            except Exception:
                logger.exception(
                    "Failed to clear axes attempts for user %s", getattr(user, "pk", None)
                )
        self.message_user(
            request, f"Deleted {total_deleted} axes attempt(s) related to selected users"
        )

    # add new actions to actions tuple
    actions = (*actions, "clear_cache_locks", "clear_axes_attempts")

    def get_urls(self) -> list:
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/rate-limits/",
                self.admin_site.admin_view(self.user_rate_limits_view),
                name="accounts_user_rate_limits",
            ),
        ]
        return custom_urls + urls

    @admin.display(description="Rate limits")
    def rate_limits_link(self, obj: User) -> str:
        try:
            url = reverse("admin:accounts_user_rate_limits", args=[obj.pk])
            return format_html('<a href="{}">Rate limits</a>', url)
        except NoReverseMatch:
            return ""

    def _ensure_action_permission(self, request: HttpRequest) -> None:
        if not (request.user.is_superuser or request.user.has_perm("accounts.change_user")):
            raise PermissionDenied()

    def user_rate_limits_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        try:
            user = User.objects.filter(pk=int(object_id)).first()
        except ValueError:
            user = None

        if not user:
            raise Http404("User not found")

        # Build context similar to the standalone admin view
        pk = str(user.pk)
        user_key = f"accounts:login:fail:user:{pk}"
        lock_key = f"accounts:login:lock:user:{pk}"

        username = getattr(user, "username", None)
        uname_info = None
        if isinstance(username, str):
            uname_hash = hashlib.sha256(username.encode()).hexdigest()[:16]
            uname_fail_key = f"accounts:login:fail:username:{uname_hash}"
            uname_lock_key = f"accounts:login:lock:username:{uname_hash}"
            uname_info = {
                "username": username,
                "failures": cache.get(uname_fail_key) or 0,
                "failures_ttl": cache.ttl(uname_fail_key) if hasattr(cache, "ttl") else None,  # pyright: ignore[reportAttributeAccessIssue]
                "lock_marker": cache.get(uname_lock_key),
                "lock_ttl": cache.ttl(uname_lock_key) if hasattr(cache, "ttl") else None,  # pyright: ignore[reportAttributeAccessIssue]
            }

        context = {
            "query": str(user.pk),
            "now": timezone.now(),
            "results": [
                {
                    "user": user,
                    "locked_until": getattr(user, "locked_until", None),
                    "failures": cache.get(user_key) or 0,
                    "failures_ttl": cache.ttl(user_key) if hasattr(cache, "ttl") else None,  # pyright: ignore[reportAttributeAccessIssue]
                    "lock_marker": cache.get(lock_key),
                    "lock_ttl": cache.ttl(lock_key) if hasattr(cache, "ttl") else None,  # pyright: ignore[reportAttributeAccessIssue]
                }
            ],
            "username_info": uname_info,
            "axes_attempts": None,
        }

        # Optional django-axes entries: show attempts for the username and recent overall
        if AccessAttempt is not None:
            try:
                attempts_by_username = (
                    AccessAttempt.objects.filter(username__icontains=username)[:25]
                    if username
                    else None
                )
                recent_attempts = AccessAttempt.objects.all().order_by("-attempt_time")[:25]
                context["axes_attempts"] = attempts_by_username
                context["axes_recent_attempts"] = recent_attempts
            except DatabaseError:
                context["axes_attempts"] = None
                context["axes_recent_attempts"] = None
        else:
            context["axes_attempts"] = None
            context["axes_recent_attempts"] = None

        return render(request, "admin/accounts/rate_limits.html", context)

    @admin.action(description="Lock selected users")
    def lock_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        """Admin action: set `locked_until` using configured lockout seconds."""
        self._ensure_action_permission(request)
        lock_seconds = getattr(settings, "ACCOUNTS_LOCKOUT_SECONDS", 15 * 60)
        lock_until = timezone.now() + timedelta(seconds=lock_seconds)

        updated = 0
        for user in queryset:
            try:
                user.locked_until = lock_until
                user.save(update_fields=["locked_until"])
                with contextlib.suppress(RuntimeError):
                    log_event(
                        logger,
                        log_name=LogName.SECURITY,
                        event_code=EventCode.SECURITY_ACCOUNT_LOCKED,
                        event="account.locked",
                        user=user,
                        object_pk=str(user.pk),
                        locked_until=lock_until.isoformat(),
                    )
                updated += 1
            except Exception:
                pk = getattr(user, "pk", None)
                logger.exception("Failed to lock user from admin action: %s", pk)

        self.message_user(request, f"Locked {updated} user(s)")

    @admin.action(description="Unlock selected users")
    def unlock_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        """Admin action: clear `locked_until` to unlock accounts."""
        self._ensure_action_permission(request)

        updated = 0
        for user in queryset:
            try:
                user.locked_until = None
                user.save(update_fields=["locked_until"])
                with contextlib.suppress(RuntimeError):
                    log_event(
                        logger,
                        log_name=LogName.SECURITY,
                        event_code=EventCode.SECURITY_ACCOUNT_UNLOCKED,
                        event="account.unlocked",
                        user=user,
                        object_pk=str(user.pk),
                    )
                updated += 1
            except Exception:
                pk = getattr(user, "pk", None)
                logger.exception("Failed to unlock user from admin action: %s", pk)

        self.message_user(request, f"Unlocked {updated} user(s)")
