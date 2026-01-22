#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
# ruff: noqa: PLC0415

import os
import sys


def main() -> None:
    """Run administrative tasks."""
    # Use the package loader `config.settings` so local and deployed processes
    # rely on the same modular settings loader. Developers can still override
    # with the `DJANGO_SETTINGS_MODULE` env var if they need a specific overlay.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
