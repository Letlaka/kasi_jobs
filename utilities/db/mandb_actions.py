from __future__ import annotations

import os
import shlex
import subprocess
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import structlog

from utilities import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName

if TYPE_CHECKING:
    from collections.abc import Callable

from django.core.management.base import CommandError

from utilities.db.db_utils import (
    create_database,
    delete_migrations_and_force_delete_db,
    force_delete_database,
    server_ping,
)
from utilities.db.pg_backup_utils import (
    build_pg_dump_command,
    build_pg_restore_command,
    ensure_directory,
    find_executable,
    get_database_settings,
    run_subprocess,
    timestamped_filename,
)

logger = get_logger(__name__)


def _ctx_value(key: str) -> str | None:
    """Safely attempt to read a value from structlog's contextvars.

    This helper tolerates different structlog versions and falls back
    to an empty dict if the context API is not present.
    """
    getter = getattr(structlog.contextvars, "get_context", None) or getattr(
        structlog.contextvars, "get_contextvars", None
    )
    if callable(getter):
        try:
            return getter().get(key)
        except (AttributeError, TypeError):
            return uuid.uuid4().hex

    ctx_private = getattr(structlog.contextvars, "_contextvars", None)
    if ctx_private is not None:
        try:
            return ctx_private.get().get(key)
        except (AttributeError, TypeError, RuntimeError):
            return None

    return None


class StyleProtocol(Protocol):
    SUCCESS: Callable[[str], str]


class StdoutProtocol(Protocol):
    def write(self, text: str) -> None: ...


Options = dict[str, Any]


def _handle_create(_options: Options, stdout: StdoutProtocol, style: StyleProtocol) -> None:
    log_event(
        logger,
        log_name=LogName.APPLICATION,
        event_code=EventCode.APPLICATION_DB_CREATE_REQUESTED,
        event="create action requested",
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )
    create_database()
    stdout.write(style.SUCCESS("Database creation complete."))
    log_event(
        logger,
        log_name=LogName.APPLICATION,
        event_code=EventCode.APPLICATION_DB_CREATED,
        event="database creation complete",
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )


def _handle_drop(options: Options, stdout: StdoutProtocol, style: StyleProtocol) -> None:
    if not options["yes"]:
        raise CommandError("'drop' is destructive. Re-run with --yes to confirm.")
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_CONFIG_CHANGED,
        event="drop action confirmed; dropping database",
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )
    force_delete_database()
    stdout.write(style.SUCCESS("Database dropped."))
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_CONFIG_CHANGED,
        event="database dropped",
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )


def _handle_reset(options: Options, stdout: StdoutProtocol, style: StyleProtocol) -> None:
    if not options["yes"]:
        raise CommandError("'reset' is destructive. Re-run with --yes to confirm.")
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_CONFIG_CHANGED,
        event="reset action confirmed; clearing migrations and dropping DB",
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )
    delete_migrations_and_force_delete_db()
    stdout.write(style.SUCCESS("Migrations cleared & DB dropped."))
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_CONFIG_CHANGED,
        event="migrations cleared and db dropped",
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )


def _handle_ping(_options: Options, stdout: StdoutProtocol, style: StyleProtocol) -> None:
    ok = server_ping()
    if ok:
        stdout.write(style.SUCCESS("PostgreSQL reachable."))
        log_event(
            logger,
            log_name=LogName.SYSTEM,
            event_code=EventCode.SYSTEM_STARTUP,
            event="postgresql reachable",
            trace_id=_ctx_value("trace_id"),
            event_id=_ctx_value("event_id") or uuid.uuid4().hex,
        )
    else:
        log_event(
            logger,
            log_name=LogName.SYSTEM,
            event_code=EventCode.SYSTEM_ERROR,
            event="postgresql not reachable",
            trace_id=_ctx_value("trace_id"),
            event_id=_ctx_value("event_id") or uuid.uuid4().hex,
        )
        raise CommandError("PostgreSQL not reachable. Check host/port/user/password.")


def _handle_backup(options: Options, stdout: StdoutProtocol, style: StyleProtocol) -> None:
    database_alias: str = options["database"]
    output_dir = Path(options["output_dir"])
    filename_prefix: str = options["prefix"]
    compression_level: int = int(options["compression"])
    include_owner_and_privileges: bool = bool(options["include_owner"])

    db = get_database_settings(database_alias)

    pg_dump_executable = find_executable("PG_DUMP_PATH", "pg_dump")

    backup_name = timestamped_filename(
        database_name=db["name"],
        prefix=filename_prefix,
        extension="dump",
    )
    backup_path = output_dir / backup_name
    ensure_directory(backup_path)

    env = os.environ.copy()
    if db["password"]:
        env["PGPASSWORD"] = db["password"]

    command = build_pg_dump_command(
        pg_dump_executable=pg_dump_executable,
        db=db,
        output_file=backup_path,
        compression_level=compression_level,
        include_owner_and_privileges=include_owner_and_privileges,
    )

    cmdline = " ".join(shlex.quote(p) for p in command)
    stdout.write(f"Running: {cmdline}")
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_EXPORT_STARTED,
        event="running pg_dump",
        command=command,
        command_line=cmdline,
        backup_path=str(backup_path),
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )
    run_subprocess(command, env)

    stdout.write(style.SUCCESS(f"Backup complete: {backup_path}"))
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_EXPORT_COMPLETED,
        event="backup complete",
        backup_path=str(backup_path),
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )


def _handle_restore(options: Options, stdout: StdoutProtocol, style: StyleProtocol) -> None:
    if not options["i_understand"]:
        raise CommandError(
            "Refusing to run without --i-understand. This will DROP and recreate objects."
        )

    database_alias: str = options["database"]
    archive_path = Path(options.get("backup") or "").expanduser().resolve()
    if not archive_path.exists():
        raise CommandError(f"Backup file not found: {archive_path}")

    db = get_database_settings(database_alias)

    pg_restore_executable = find_executable("PG_RESTORE_PATH", "pg_restore")

    env = os.environ.copy()
    if db["password"]:
        env["PGPASSWORD"] = db["password"]

    command = build_pg_restore_command(
        pg_restore_executable=pg_restore_executable,
        db=db,
        archive_file=archive_path,
        create_database_first=bool(options["create_db"]),
        parallel_jobs=int(options["jobs"]),
    )

    cmdline = " ".join(shlex.quote(p) for p in command)
    stdout.write(f"Running: {cmdline}")
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_EXPORT_STARTED,
        event="running pg_restore",
        command=command,
        command_line=cmdline,
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )
    try:
        subprocess.run(command, env=env, check=True)  # noqa: S603
    except subprocess.CalledProcessError as exc:
        log_event(
            logger,
            log_name=LogName.SYSTEM,
            event_code=EventCode.SYSTEM_ERROR,
            event="pg_restore failed",
            exit_code=exc.returncode,
            command_line=cmdline,
            trace_id=_ctx_value("trace_id"),
            event_id=_ctx_value("event_id") or uuid.uuid4().hex,
        )
        raise CommandError(f"Restore failed with exit code {exc.returncode}") from exc

    stdout.write(style.SUCCESS("Restore complete."))
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_EXPORT_COMPLETED,
        event="restore complete",
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )


def perform_action(
    action: str,
    options: Options,
    stdout: StdoutProtocol,
    style: StyleProtocol,
) -> None:
    """
    Dispatch the requested action to the appropriate handler.
    Behaviour is identical to the original if/elif chain in Command.handle().
    """
    if action == "create":
        _handle_create(options, stdout, style)
    elif action == "drop":
        _handle_drop(options, stdout, style)
    elif action == "reset":
        _handle_reset(options, stdout, style)
    elif action == "ping":
        _handle_ping(options, stdout, style)
    elif action == "backup":
        _handle_backup(options, stdout, style)
    elif action == "restore":
        _handle_restore(options, stdout, style)
    else:
        raise CommandError(f"Unknown action: {action}")
