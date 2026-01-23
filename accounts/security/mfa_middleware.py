from __future__ import annotations

from collections.abc import Callable

# Import allauth MFA pieces lazily inside the request handler to avoid
# triggering allauth.mfa model imports at module import time. Importing
# `allauth.mfa` raises ImproperlyConfigured when MFA isn't enabled, which
# would break startup.
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


class RequireMFAForAdminMiddleware:
    """Require configured MFA for access to the Django admin in production.

    Behaviour:
    - No-op when ``settings.DEBUG`` is True (development bypass).
    - When a request targets ``/admin/`` and the user is authenticated and
      is staff, require that ``allauth.mfa`` reports MFA enabled for the
      user. If not enabled, redirect to the MFA index/setup page.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Bypass in development / debug
        if getattr(settings, "DEBUG", False):
            return self.get_response(request)

        # Only enforce for admin paths
        path = getattr(request, "path", "")
        if not isinstance(path, str) or not path.startswith("/admin/"):
            return self.get_response(request)

        user = getattr(request, "user", None)
        # If user is not authenticated or not staff, let normal admin login flow run
        if not (
            user and getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False)
        ):
            return self.get_response(request)

        # Determine whether allauth.mfa is enabled. Import the lightweight
        # allauth.app_settings first — only if MFA is enabled do we import the
        # heavier MFA modules which may import database models.
        try:
            from allauth import app_settings as allauth_app_settings
        except Exception:
            # allauth not installed; allow request to proceed (auth will handle)
            return self.get_response(request)

        if not getattr(allauth_app_settings, "MFA_ENABLED", False):
            # MFA not enabled in configuration; nothing to enforce.
            return self.get_response(request)

        try:
            from allauth.mfa.adapter import get_adapter as get_mfa_adapter

            adapter = get_mfa_adapter()
        except Exception:
            # If MFA subsystem cannot be loaded, skip enforcement to avoid
            # failing startup; authentication will still protect admin.
            return self.get_response(request)

        # If MFA is enabled, require the user to have an authenticator.
        try:
            if adapter.is_mfa_enabled(user):
                return self.get_response(request)
        except Exception:
            # On error while checking MFA status, redirect to login as safe fallback
            return redirect(reverse("account_login"))

        # Redirect to the MFA index (accounts/2fa/) to let the user configure MFA
        index_url = reverse("mfa_index")
        # Preserve next parameter so user returns to original admin page after setup
        return redirect(f"{index_url}?next={request.path}")
