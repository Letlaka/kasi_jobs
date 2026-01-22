import os

from celery import Celery

"""
Prefer an explicit env var, otherwise default to the project settings package loader.
This avoids hardcoding and ensures Celery uses the same
`config.settings` package loader used by ASGI/WSGI/manage.
"""
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings")
)

app = Celery("core")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
