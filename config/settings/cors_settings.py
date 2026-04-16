from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from .env import env

# Read values from environment
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = env.bool("CORS_ALLOW_CREDENTIALS")
CORS_ALLOW_HEADERS = env.list("CORS_ALLOW_HEADERS")
CORS_ALLOW_METHODS = env.list("CORS_ALLOW_METHODS")
CORS_URLS_REGEX = env("CORS_URLS_REGEX")

# Disallow overly permissive CORS in production. Use explicit allowed origins.
is_debug = env.bool("DJANGO_DEBUG")
if not is_debug:
    if CORS_ALLOW_ALL_ORIGINS:
        raise ImproperlyConfigured(
            "CORS_ALLOW_ALL_ORIGINS=True is not permitted in production. "
            "Set CORS_ALLOWED_ORIGINS to a comma-separated list of allowed origins."
        )
    if not CORS_ALLOWED_ORIGINS:
        raise ImproperlyConfigured(
            "CORS_ALLOWED_ORIGINS must be set in production and cannot be empty."
        )
