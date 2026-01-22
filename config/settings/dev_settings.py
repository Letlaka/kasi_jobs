from __future__ import annotations

from .base_settings import *  # noqa: F403
from .base_settings import env

DEBUG = True
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "devbox"])
WHITENOISE_AUTOREFRESH = True
LOG_RENDER_MODE = env("LOG_RENDER_MODE", default="console")

AUDITLOG_INCLUDE_ALL_MODELS = True

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS")

CORS_ALLOW_ALL_ORIGINS = True

AXES_FAILURE_LIMIT = 3
