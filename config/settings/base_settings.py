from __future__ import annotations

import os
from pathlib import Path

# Local modular settings (import modules; we'll merge their UPPERCASE symbols
# into this namespace below)
from . import (
    axes_settings,
    cache_settings,
    celery_settings,
    cors_settings,
    csp_settings,
    database_settings,
    drf_settings,
    logging_settings,
    security_settings,
    static_settings,
)

try:
    from .env import env
except (ImportError, ModuleNotFoundError):

    class _FallbackEnv:
        def __init__(self) -> None:
            self._os = os.environ

        def __call__(self, key: str, default: str | None = None) -> str | None:
            return self._os.get(key, default)

        def bool(self, key: str, *, default: bool = False) -> bool:
            v = self._os.get(key)
            if v is None:
                return default
            return str(v).lower() in ("1", "true", "yes", "on")

        def int(self, key: str, *, default: int = 0) -> int:
            v = self._os.get(key)
            if v is None:
                return default
            try:
                return int(v)
            except (TypeError, ValueError):
                return default

        def list(self, key: str, *, default: list[str] | None = None) -> list[str]:
            v = self._os.get(key)
            if v is None:
                return [] if default is None else default
            return [p.strip() for p in v.split(",") if p.strip()]

    env = _FallbackEnv()


# Base dir
BASE_DIR = Path(__file__).resolve().parent.parent

# Merge UPPERCASE symbols from modular settings into this module namespace
for _mod in (
    database_settings,
    cache_settings,
    celery_settings,
    security_settings,
    cors_settings,
    csp_settings,
    drf_settings,
    axes_settings,
    static_settings,
    logging_settings,
):
    for _name, _value in vars(_mod).items():
        if _name.isupper():
            globals()[_name] = _value


# Basic / core settings
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# Internationalisation
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Johannesburg"
USE_I18N = True
USE_TZ = True


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.sites",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "drf_spectacular",
    "crispy_forms",
    "crispy_bootstrap5",
    "corsheaders",
    "allauth",
    "allauth.account",
    "auditlog",
    "simple_history",
    "csp",
    "django_countries",
    "phonenumber_field",
    "django_filters",
    "django_structlog",
    "django_prometheus",
    "axes",
    # Local apps
    "core",
    "accounts",
    "app_reports",
    "departments",
    "utilities",
]


raw_site_id = env("SITE_ID")
SITE_ID = int(raw_site_id) if raw_site_id not in (None, "") else 1


MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "csp.middleware.CSPMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_structlog.middlewares.RequestMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]


ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Authentication and passwords
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# django-allauth sane defaults
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

# allauth adapter to add project-specific hooks (logging, audit)
ACCOUNT_ADAPTER = "accounts.allauth_adapter.CustomAccountAdapter"

AUTH_USER_MODEL = "accounts.User"

(BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)

# Email & contact settings
EMAIL_BACKEND = env("EMAIL_BACKEND")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
CONTACT_EMAIL = env("CONTACT_EMAIL")
SECURITY_TEAM_EMAIL = env("SECURITY_TEAM_EMAIL")


# HMAC / signing settings
HMAC_SECRET_KEY = env("HMAC_SECRET_KEY")


# django-auditlog global settings (POPIA / privacy friendly defaults)
AUDITLOG_INCLUDE_ALL_MODELS = env.bool("AUDITLOG_INCLUDE_ALL_MODELS")
AUDITLOG_EXCLUDE_TRACKING_FIELDS = env.list("AUDITLOG_EXCLUDE_TRACKING_FIELDS")
AUDITLOG_DISABLE_REMOTE_ADDR = env.bool("AUDITLOG_DISABLE_REMOTE_ADDR")


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
