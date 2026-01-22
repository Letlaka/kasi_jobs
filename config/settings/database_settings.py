from __future__ import annotations

from pathlib import Path

from .env import env

# Base dir for fallback defaults
BASE_DIR = Path(__file__).resolve().parent.parent.parent

default_db_name = f"{BASE_DIR.name}_db"

_pg_host = env("POSTGRES_HOST")
if _pg_host:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", default=default_db_name),
            "USER": env("POSTGRES_USER"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
            "HOST": _pg_host,
            "PORT": env("POSTGRES_PORT"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }
    }
