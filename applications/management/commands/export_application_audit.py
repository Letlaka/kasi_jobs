from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO, cast

if TYPE_CHECKING:
    import argparse
    from collections.abc import Iterable, Iterator

from applications.models import ApplicationAction
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Export ApplicationAction audit rows for a given application id as JSON or CSV"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("application_id", type=int, help="Application id to export audit for")
        parser.add_argument(
            "--format", choices=("json", "csv"), default="json", help="Output format (json|csv)"
        )
        parser.add_argument("--output", type=str, help="Output file path (defaults to stdout)")

    def handle(self, *_args: object, **options: Any) -> None:  # noqa: ANN401
        app_id = options.get("application_id")
        fmt = options.get("format")
        out_path = options.get("output")

        qs = ApplicationAction.objects.filter(application_id=app_id).order_by("created_at")  # type: ignore[attr-defined]

        if not qs.exists():
            raise CommandError(f"no audit rows found for application id={app_id}")

        if fmt == "json":
            data = serializers.serialize("json", qs, indent=2)
            if out_path:
                Path(str(out_path)).expanduser().open("w", encoding="utf-8").write(data)
            else:
                self.stdout.write(data)
            return

        # CSV format
        fields = ["id", "application_id", "action", "performed_by_id", "created_at", "metadata"]

        def iter_rows(qs: Iterable[object]) -> Iterator[dict]:
            for obj in qs:
                performed_at = getattr(obj, "performed_at", None)
                yield {
                    "id": getattr(obj, "id", None),
                    "application_id": getattr(obj, "application_id", None)
                    or getattr(obj, "application", None),
                    "action": getattr(obj, "action", None),
                    "performed_by_id": getattr(getattr(obj, "performed_by", None), "id", None),
                    "created_at": performed_at.isoformat() if performed_at else None,
                    "metadata": json.dumps(getattr(obj, "metadata", {}) or {}),
                }

        if out_path:
            with Path(str(out_path)).expanduser().open("w", encoding="utf-8", newline="") as out_f:
                writer = csv.DictWriter(out_f, fieldnames=fields)
                writer.writeheader()
                for row in iter_rows(qs):
                    writer.writerow(row)
        else:
            # django BaseCommand.stdout is an OutputWrapper; cast to TextIO for csv writer
            writer = csv.DictWriter(cast("TextIO", self.stdout), fieldnames=fields)
            writer.writeheader()
            for row in iter_rows(qs):
                writer.writerow(row)
