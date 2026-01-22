"""Load settings from modular files.

This package loader prefers `base_settings.py` and overlays an environment
specific file (`dev_settings.py` or `prod_settings.py`). It copies public
(UPPERCASE) symbols into the package module namespace so Django can import
`config.settings` as before.

If `base_settings.py` is missing we fall back to the legacy single-file
`config/settings.py` for compatibility.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).resolve().parent

BASE_PY = ROOT / "base_settings.py"
DEV_PY = ROOT / "dev_settings.py"
PROD_PY = ROOT / "prod_settings.py"


def _load_module_from_path(path: Path, module_name: str) -> ModuleType | None:
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(path)
    spec.loader.exec_module(module)
    return module


# Load base settings (preferred), fall back to legacy settings.py
base_module = _load_module_from_path(BASE_PY, "config.settings.base")
if base_module is None:
    legacy = ROOT.parent / "settings.py"
    base_module = _load_module_from_path(legacy, "config.settings._legacy")

if base_module is not None:
    for name, value in vars(base_module).items():
        if name.isupper():
            globals()[name] = value

    # Choose overlay: explicit DJANGO_ENV wins; otherwise use DJANGO_DEBUG
    env_name = os.environ.get("DJANGO_ENV")
    if not env_name:
        dj_debug = os.environ.get("DJANGO_DEBUG")
        if dj_debug and str(dj_debug).lower() in ("1", "true", "yes", "on"):
            env_name = "dev"
        else:
            env_name = "prod"

    overlay_path = DEV_PY if env_name == "dev" else PROD_PY
    overlay_module = _load_module_from_path(overlay_path, f"config.settings.{env_name}")
    if overlay_module is not None:
        for name, value in vars(overlay_module).items():
            if name.isupper():
                globals()[name] = value

    __loaded_settings_module__: ModuleType | None = overlay_module or base_module
else:
    __loaded_settings_module__ = None
