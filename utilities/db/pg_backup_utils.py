from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError
from django.utils import timezone

from utilities import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName

logger = get_logger(__name__)


def get_database_settings(alias: str = "default") -> dict[str, str]:
    try:
        db = settings.DATABASES[alias]
    except KeyError as exc:
        raise CommandError(f"Database alias '{alias}' not found in settings.DATABASES") from exc

    return {
        "name": db.get("NAME") or "",
        "user": db.get("USER") or "",
        "password": db.get("PASSWORD") or "",
        "host": db.get("HOST") or "127.0.0.1",
        "port": str(db.get("PORT") or "5432"),
    }


def ensure_directory(path: Path) -> None:
    """Ensure the parent directory for `path` exists.

    The function expects `path` to be the target file path and will
    create the parent directory(s) as needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    log_event(
        logger,
        log_name=LogName.SYSTEM,
        event_code=EventCode.SYSTEM_STARTUP,
        event="Ensured directory exists",
        path=str(path.parent),
    )


def find_executable(preferred_env_var: str, fallback_name: str) -> str:
    explicit_path = os.environ.get(preferred_env_var)
    if explicit_path:
        exe = Path(explicit_path)
        if exe.exists():
            log_event(
                logger,
                log_name=LogName.AUDIT,
                event_code=EventCode.AUDIT_CONFIG_CHANGED,
                event="Using explicit executable from env",
                env_var=preferred_env_var,
                path=str(exe),
            )
            return str(exe)

    resolved = shutil.which(fallback_name)
    if not resolved:
        raise CommandError(
            f"Could not find '{fallback_name}'. Add it to PATH or set {preferred_env_var} to the full executable path."  # noqa: E501
        )
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_CONFIG_CHANGED,
        event="Found executable in PATH",
        executable=resolved,
    )
    return resolved


def timestamped_filename(database_name: str, prefix: str, extension: str) -> str:
    stamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    base = prefix or database_name
    return f"{base}_{stamp}.{extension.lstrip('.')}"


def build_pg_dump_command(
    pg_dump_executable: str,
    db: dict[str, str],
    output_file: Path,
    compression_level: int,
    *,
    include_owner_and_privileges: bool,
) -> list[str]:
    args = [
        pg_dump_executable,
        "-h",
        db["host"],
        "-p",
        db["port"],
        "-U",
        db["user"],
        "-d",
        db["name"],
        "-Fc",
        "-Z",
        str(compression_level),
        "-f",
        str(output_file),
    ]
    if not include_owner_and_privileges:
        args += ["--no-owner", "--no-privileges"]
    return args


def build_pg_restore_command(
    pg_restore_executable: str,
    db: dict[str, str],
    archive_file: Path,
    *,
    create_database_first: bool,
    parallel_jobs: int,
) -> list[str]:
    base_args = [
        pg_restore_executable,
        "-h",
        db["host"],
        "-p",
        db["port"],
        "-U",
        db["user"],
        "-j",
        str(parallel_jobs),
        "--clean",
        "--if-exists",
    ]
    include_owner_and_privileges = bool(db.get("include_owner_and_privileges", False))

    if not include_owner_and_privileges:
        base_args += ["--no-owner", "--no-privileges"]

    if create_database_first:
        base_args += ["-C", "-d", "postgres"]
    else:
        base_args += ["-d", db["name"]]

    base_args.append(str(archive_file))
    return base_args


def run_subprocess(command: list[str], env: dict[str, str]) -> None:
    cmdline = " ".join(shlex.quote(p) for p in command)
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_EXPORT_STARTED,
        event="Running subprocess",
        command=command,
        command_line=cmdline,
    )
    try:
        subprocess.run(command, env=env, check=True)  # noqa: S603
        log_event(
            logger,
            log_name=LogName.AUDIT,
            event_code=EventCode.AUDIT_EXPORT_COMPLETED,
            event="Subprocess completed successfully",
            command_line=cmdline,
        )
    except subprocess.CalledProcessError as exc:
        pretty = " ".join(shlex.quote(p) for p in command)
        log_event(
            logger,
            log_name=LogName.SYSTEM,
            event_code=EventCode.SYSTEM_ERROR,
            event="Subprocess failed",
            exit_code=exc.returncode,
            command_line=pretty,
        )
        raise CommandError(f"Command failed with exit code {exc.returncode}: {pretty}") from exc
