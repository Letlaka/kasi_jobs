from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import argparse

from django.conf import settings
from django.core.management.base import BaseCommand
from services.dispatch import count_background_receivers


class Command(BaseCommand):
    help = (
        "Check that background task receivers are registered (used for readiness/startup checks)."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--fail-on-zero",
            action="store_true",
            help="Exit with non-zero code if no receivers are registered.",
        )

    def handle(self, **options: Any) -> None:  # noqa: ANN401
        receivers = count_background_receivers()
        self.stdout.write(f"background_task_receivers={receivers}")
        env = getattr(settings, "ENVIRONMENT", None) or getattr(settings, "ENV", "local")

        # Default behavior: in production, warn and exit non-zero if zero receivers.
        should_fail = False
        if options.get("fail_on_zero") or env == "production":
            should_fail = receivers == 0

        if should_fail:
            self.stderr.write("no background task receivers registered")
            raise SystemExit(2)

        # success
