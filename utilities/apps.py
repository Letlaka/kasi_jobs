import contextlib
import importlib

from django.apps import AppConfig, apps

# Defer importing models until `ready()` to avoid AppRegistryNotReady during
# app module import time.
_auditlog_registry: object | None = None


class UtilitiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "utilities"

    def ready(self) -> None:
        """Register concrete models that inherit `AuditedModel` with auditlog.

        This allows project models to simply inherit `utilities.models.AuditedModel`
        to opt-in to both django-simple-history (via the `history` field) and
        django-auditlog (registered here at startup).
        """
        _audited_model: object | None = None
        with contextlib.suppress(ImportError):
            _models_mod = importlib.import_module("utilities.models")
            _audited_model = getattr(_models_mod, "AuditedModel", None)

        _auditlog_registry_local: object | None = None
        with contextlib.suppress(ImportError):
            _auditlog_registry_local = importlib.import_module("auditlog.registry")

        for model in apps.get_models():
            if getattr(model._meta, "abstract", False):
                continue
            if not isinstance(model, type):
                continue
            if _auditlog_registry_local is None:
                continue
            if not isinstance(_audited_model, type):
                continue
            if not issubclass(model, _audited_model):
                continue

            auditlog = getattr(_auditlog_registry_local, "auditlog", None)
            if auditlog is not None:
                with contextlib.suppress(Exception):
                    auditlog.register(model)
