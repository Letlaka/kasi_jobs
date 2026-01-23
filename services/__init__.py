"""Services package init.

This makes `services` an explicit package so module names inside it
are resolved as `services.*` (avoids mypy duplicate-module issues).
"""

__all__ = [
    "applications_service",
    "dispatch",
]

# NOTE: don't import submodules at package import time. Importing
# service modules here causes Django to try loading models during
# app registry population which raises `AppRegistryNotReady`.
# Import submodules explicitly where needed.
