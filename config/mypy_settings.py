import os
from pathlib import Path

try:
    from .settings.env import env as project_env
except (ImportError, ModuleNotFoundError):
    project_env = None

BASE_DIR = Path(__file__).resolve().parent.parent

if project_env is not None:
    env = project_env
else:
    try:
        import environ as _environ

        env = _environ.Env(
            SITE_ID=(int, 1),
            DEBUG=(bool, False),
            EMAIL_PORT=(int, 587),
            EMAIL_USE_TLS=(bool, True),
            POSTGRES_PORT=(int, 5432),
            CELERY_TASK_RESULT_EXPIRES=(int, 3600),
        )
        import contextlib

        # Only load .env when developing locally so CI/production secrets are
        # not overridden by a repository .env file or local file.
        if os.getenv("DJANGO_ENV", "development") == "development":
            with contextlib.suppress(Exception):
                env.read_env(BASE_DIR / ".env")
    except (ImportError, ModuleNotFoundError):
        env = None

if env is not None:
    SECRET_KEY = env("DJANGO_SECRET_KEY")

DEBUG = False


INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

MIDDLEWARE: list[str] = []
ROOT_URLCONF: str | None = None

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
