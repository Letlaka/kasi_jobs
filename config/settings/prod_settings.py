from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from .base_settings import *  # noqa: F403
from .base_settings import env

# Production must be explicit about these values. We provide secure defaults
# but also fail-fast if any setting ends up insecure.
DEBUG = False

# Secure defaults for cookie flags and SSL enforcement
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)

# HSTS defaults (1 year) and include-subdomains/preload are conservative defaults
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=True)

SECURE_CONTENT_TYPE_NOSNIFF = env.bool("SECURE_CONTENT_TYPE_NOSNIFF", default=True)
SECURE_BROWSER_XSS_FILTER = env.bool("SECURE_BROWSER_XSS_FILTER", default=True)

X_FRAME_OPTIONS = env("X_FRAME_OPTIONS") or "DENY"

CSP_REPORT_ONLY = env.bool("CSP_REPORT_ONLY", default=False)

# Fail-fast if critical production security settings are not enabled
if DEBUG:
    raise ImproperlyConfigured("Production settings must set DEBUG=False")

if not (SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE and SECURE_SSL_REDIRECT):
    raise ImproperlyConfigured(
        "Insecure production configuration: set SESSION_COOKIE_SECURE=True, "
        "CSRF_COOKIE_SECURE=True and SECURE_SSL_REDIRECT=True in the environment."
    )

if not isinstance(SECURE_HSTS_SECONDS, int) or SECURE_HSTS_SECONDS <= 0:
    raise ImproperlyConfigured("SECURE_HSTS_SECONDS must be a positive integer in production")

LOG_RENDER_MODE = env("LOG_RENDER_MODE", default="json")

CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS")
