from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import argparse

from applications.models import Application
from django.core import serializers
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = "Export and delete old Application rows (archive)."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--days", type=int, default=365, help="Archive applications older than DAYS"
        )
        parser.add_argument("--batch-size", type=int, default=1000, help="Rows per batch")
        parser.add_argument(
            "--output-dir", type=str, default="./archives", help="Directory to write archive files"
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Do not delete rows; only report"
        )

    def handle(self, *_args: object, **options: Any) -> None:  # noqa: ANN401
        days = int(options.get("days", 365))
        batch_size = int(options.get("batch_size", 1000))
        out_dir = Path(str(options.get("output_dir", "./archives"))).expanduser()
        dry_run = bool(options.get("dry_run", False))

        cutoff = timezone.now() - timedelta(days=days)
        out_dir.mkdir(parents=True, exist_ok=True)

        qs = Application.objects.filter(applied_at__lt=cutoff).order_by("applied_at")  # type: ignore[attr-defined]
        total = qs.count()
        self.stdout.write(f"Found {total} applications older than {days} days (before {cutoff}).")
        if total == 0:
            return

        batch_index = 0
        while True:
            batch = list(qs[:batch_size])
            if not batch:
                break
            batch_index += 1
            filename = out_dir / f"applications_archive_{cutoff.date()}_{batch_index}.json"
            self.stdout.write(f"Exporting batch {batch_index} ({len(batch)}) to {filename}")

            # serialize to JSON (Django serialization preserves FK ids)
            data = serializers.serialize("json", batch)
            # write compressed-friendly JSON (newline-delimited objects)
            with filename.open("w", encoding="utf-8") as f:
                f.write(data)

            if dry_run:
                self.stdout.write("Dry-run: not deleting rows")
            else:
                ids = [o.pk for o in batch]
                # delete in a short transaction to avoid long locks
                with transaction.atomic():
                    Application.objects.filter(pk__in=ids).delete()  # type: ignore[attr-defined]
                self.stdout.write(f"Deleted {len(ids)} rows (batch {batch_index})")

        self.stdout.write("Archive run complete.")
