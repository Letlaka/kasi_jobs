import contextlib

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Accounts"

    def ready(self) -> None:
        # Import signal handlers to ensure they're registered on app startup
        with contextlib.suppress(Exception):
            import accounts.signals  # noqa: F401,PLC0415 - import inside ready required by Django
