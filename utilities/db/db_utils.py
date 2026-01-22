from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
import structlog
from django.conf import settings
from psycopg import sql

from utilities import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName


def _ctx_value(key: str) -> str | None:
    getter = getattr(structlog.contextvars, "get_context", None) or getattr(
        structlog.contextvars, "get_contextvars", None
    )
    if callable(getter):
        try:
            return getter().get(key)  # pyright: ignore[reportAttributeAccessIssue]
        except (AttributeError, TypeError):
            pass

    ctx_private = getattr(structlog.contextvars, "_contextvars", None)
    if ctx_private is not None:
        try:
            return ctx_private.get().get(key)
        except (AttributeError, TypeError, RuntimeError):
            return uuid.uuid4().hex

    return uuid.uuid4().hex


logger = get_logger(__name__)


@dataclass(frozen=True)
class DatabaseConfig:
    """
    Typed configuration for connecting to PostgreSQL, derived from Django settings.
    """

    database_host: str
    database_port: int
    database_user: str
    database_password: str
    database_name: str


def _get_default_db_config() -> DatabaseConfig:
    """
    Read and validate the default database config from Django settings.
    Only supports the built-in PostgreSQL backend.
    """
    database_settings: dict[str, Any] = settings.DATABASES.get("default", {})
    engine: str = database_settings.get("ENGINE", "")
    if "django.db.backends.postgresql" not in engine:
        raise ValueError("This utility only supports the PostgreSQL backend.")

    return DatabaseConfig(
        database_host=str(database_settings.get("HOST") or "127.0.0.1"),
        database_port=int(database_settings.get("PORT") or 5432),
        database_user=str(database_settings.get("USER") or ""),
        database_password=str(database_settings.get("PASSWORD") or ""),
        database_name=str(database_settings.get("NAME") or ""),
    )


def _connect_as_admin(target_database_name: str, config: DatabaseConfig) -> psycopg.Connection:
    """
    Open a psycopg3 connection to the given database using the credentials from settings.
    Uses autocommit to allow DDL statements without explicit transactions.
    """
    connection_event = (
        f"Connecting to Postgres at {config.database_host}:{config.database_port} "
        f"as {config.database_user or '<empty-user>'}"
    )
    log_event(
        logger,
        log_name=LogName.SYSTEM,
        event_code=EventCode.SYSTEM_STARTUP,
        event=connection_event,
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )
    connection = psycopg.connect(
        dbname=target_database_name,
        user=config.database_user,
        password=config.database_password,
        host=config.database_host,
        port=config.database_port,
        connect_timeout=10,
    )
    connection.autocommit = True
    return connection


def server_ping() -> bool:
    """
    Try a lightweight connection to the 'postgres' maintenance database.
    Returns True on success, False on failure. Logs the exact exception.
    """
    config = _get_default_db_config()
    try:
        with _connect_as_admin("postgres", config) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            _ = cursor.fetchone()
        log_event(
            logger,
            log_name=LogName.SYSTEM,
            event_code=EventCode.SYSTEM_STARTUP,
            event="Successfully connected to PostgreSQL server.",
            trace_id=_ctx_value("trace_id"),
            event_id=_ctx_value("event_id") or uuid.uuid4().hex,
        )
        return True
    except psycopg.Error as error:
        log_event(
            logger,
            log_name=LogName.SYSTEM,
            event_code=EventCode.SYSTEM_ERROR,
            event="PostgreSQL ping failed",
            error=str(error),
            trace_id=_ctx_value("trace_id"),
            event_id=_ctx_value("event_id"),
        )
        return False


def _database_exists(connection: psycopg.Connection, database_name: str) -> bool:
    """
    Check if a database exists on the server.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (database_name,))
        return cursor.fetchone() is not None


def create_database() -> None:
    """
    Create the Django project's database if it does not already exist.
    Requires that the connecting role has CREATEDB privilege.
    """
    config = _get_default_db_config()
    if not config.database_name:
        raise ValueError("Database name is empty; check settings.DATABASES['default']['NAME'].")

    try:
        with _connect_as_admin("postgres", config) as connection:
            if _database_exists(connection, config.database_name):
                log_event(
                    logger,
                    log_name=LogName.APPLICATION,
                    event_code=EventCode.APPLICATION_DB_ALREADY_EXISTS,
                    event=f"Database {config.database_name!r} already exists.",
                )
                return

            log_event(
                logger,
                log_name=LogName.APPLICATION,
                event_code=EventCode.APPLICATION_DB_CREATE_REQUESTED,
                event=f"Creating database {config.database_name!r} …",
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(config.database_name))
                )
            log_event(
                logger,
                log_name=LogName.APPLICATION,
                event_code=EventCode.APPLICATION_DB_CREATED,
                event=f"Database {config.database_name!r} created successfully.",
            )
    except psycopg.OperationalError as error:
        log_event(
            logger,
            log_name=LogName.SYSTEM,
            event_code=EventCode.SYSTEM_ERROR,
            event="Could not connect to server to create database",
            error=str(error),
        )
        raise
    except psycopg.Error as error:
        log_event(
            logger,
            log_name=LogName.SYSTEM,
            event_code=EventCode.SYSTEM_ERROR,
            event="Create database failed",
            error=str(error),
        )
        raise


def _terminate_backends(connection: psycopg.Connection, database_name: str) -> None:
    """
    Terminate active connections to the given database (except our own).
    """
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_CONFIG_CHANGED,
        event=f"Terminating active connections to {database_name}",
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id"),
    )
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s
              AND pid <> pg_backend_pid();
            """,
            (database_name,),
        )


def force_delete_database() -> None:
    """
    Drop the Django project's database, terminating connections first when necessary.
    Uses DROP DATABASE … WITH (FORCE) if supported; otherwise falls back to manual termination.
    """
    config = _get_default_db_config()
    if not config.database_name:
        raise ValueError("Database name is empty; check settings.DATABASES['default']['NAME'].")

    try:
        with _connect_as_admin("postgres", config) as connection:
            if not _database_exists(connection, config.database_name):
                log_event(
                    logger,
                    log_name=LogName.AUDIT,
                    event_code=EventCode.AUDIT_CONFIG_CHANGED,
                    event=f"Database {config.database_name!r} does not exist.",
                    trace_id=_ctx_value("trace_id"),
                    event_id=_ctx_value("event_id"),
                )
                return

            try:
                log_event(
                    logger,
                    log_name=LogName.AUDIT,
                    event_code=EventCode.AUDIT_CONFIG_CHANGED,
                    event=f"Dropping database {config.database_name!r} with FORCE",
                    trace_id=_ctx_value("trace_id"),
                    event_id=_ctx_value("event_id") or uuid.uuid4().hex,
                )
                with connection.cursor() as cursor:
                    cursor.execute(
                        sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                            sql.Identifier(config.database_name)
                        )
                    )
                log_event(
                    logger,
                    log_name=LogName.AUDIT,
                    event_code=EventCode.AUDIT_CONFIG_CHANGED,
                    event=f"Database {config.database_name!r} dropped",
                    trace_id=_ctx_value("trace_id"),
                    event_id=_ctx_value("event_id") or uuid.uuid4().hex,
                )
                return
            except psycopg.Error:
                log_event(
                    logger,
                    log_name=LogName.AUDIT,
                    event_code=EventCode.AUDIT_CONFIG_CHANGED,
                    event="WITH (FORCE) not available; trying manual termination",
                    trace_id=_ctx_value("trace_id"),
                    event_id=_ctx_value("event_id") or uuid.uuid4().hex,
                )

            _terminate_backends(connection, config.database_name)
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("DROP DATABASE {}").format(sql.Identifier(config.database_name))
                )
            log_event(
                logger,
                log_name=LogName.AUDIT,
                event_code=EventCode.AUDIT_CONFIG_CHANGED,
                event=f"Database {config.database_name!r} dropped",
                trace_id=_ctx_value("trace_id"),
                event_id=_ctx_value("event_id") or uuid.uuid4().hex,
            )
    except psycopg.OperationalError as error:
        log_event(
            logger,
            log_name=LogName.SYSTEM,
            event_code=EventCode.SYSTEM_ERROR,
            event="Could not connect to server to drop database",
            error=str(error),
            trace_id=_ctx_value("trace_id"),
            event_id=_ctx_value("event_id"),
        )
        raise
    except psycopg.Error as error:
        log_event(
            logger,
            log_name=LogName.SYSTEM,
            event_code=EventCode.SYSTEM_ERROR,
            event="Drop database failed",
            error=str(error),
            trace_id=_ctx_value("trace_id"),
            event_id=_ctx_value("event_id"),
        )
        raise


def _find_project_root_candidate() -> Path:
    """Find a sensible project root by looking for manage.py or settings.py.

    This is a best-effort fallback when `settings.BASE_DIR` is not present.
    """
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "manage.py").exists() or (parent / "settings.py").exists():
            return parent
    return Path.cwd()


def _gather_app_dirs(root: Path) -> list[Path]:
    """Return application directories under `root` containing a `migrations` folder."""
    return [d for d in root.iterdir() if (d / "migrations").is_dir() and d.name != ".venv"]


def _remove_migration_files(migrations_path: Path) -> None:
    """Remove python migration files (except __init__.py) and pyc files under a migrations path."""
    for py_file in migrations_path.glob("*.py"):
        if py_file.name != "__init__.py":
            py_file.unlink(missing_ok=True)
    for pyc_file in migrations_path.glob("*.pyc"):
        pyc_file.unlink(missing_ok=True)


def _confirm_deletion_prompt() -> bool:
    """Prompt the user to confirm deletion; return True if confirmed."""
    confirm = input("Type 'yes' to confirm deletion of migration files in these directories: ")
    return confirm.strip().lower() == "yes"


def _perform_deletion(project_root: Path, *, force: bool) -> bool:
    """Perform the deletion of migration files. Returns True if deletion occurred.

    This helper centralises the work so the public API function remains thin
    and easy to reason about (reducing cognitive complexity).
    """
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_CONFIG_CHANGED,
        event="Preparing to delete migration files",
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )

    app_dirs = _gather_app_dirs(project_root)
    if not app_dirs:
        log_event(
            logger,
            log_name=LogName.AUDIT,
            event_code=EventCode.AUDIT_CONFIG_CHANGED,
            event="No app directories with migrations found",
            trace_id=_ctx_value("trace_id"),
            event_id=_ctx_value("event_id") or uuid.uuid4().hex,
        )
        return False

    _log_app_dirs(app_dirs)

    if not _confirm_and_delete(force=force):
        log_event(
            logger,
            log_name=LogName.AUDIT,
            event_code=EventCode.AUDIT_CONFIG_CHANGED,
            event="Migration file deletion aborted by user",
            trace_id=_ctx_value("trace_id"),
            event_id=_ctx_value("event_id") or uuid.uuid4().hex,
        )
        return False

    _delete_migrations_for_dirs(app_dirs)

    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_CONFIG_CHANGED,
        event="All migration files deleted",
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )
    return True


def _log_app_dirs(app_dirs: list[Path]) -> None:
    """Log the list of application directories that will be affected."""
    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_CONFIG_CHANGED,
        event=(
            "The following app directories will have their migration files deleted "
            "(except __init__.py):"
        ),
        trace_id=_ctx_value("trace_id"),
        event_id=_ctx_value("event_id") or uuid.uuid4().hex,
    )
    for app_dir in app_dirs:
        log_event(
            logger,
            log_name=LogName.AUDIT,
            event_code=EventCode.AUDIT_CONFIG_CHANGED,
            event=f"app_dir: {app_dir}",
            trace_id=_ctx_value("trace_id"),
            event_id=_ctx_value("event_id") or uuid.uuid4().hex,
        )


def _delete_migrations_for_dirs(app_dirs: list[Path]) -> None:
    """Remove migration files for every app directory in the list."""
    for app_dir in app_dirs:
        migrations_path = app_dir / "migrations"
        _remove_migration_files(migrations_path)


def _confirm_and_delete(*, force: bool) -> bool:
    """Return True when deletion should proceed (either forced or confirmed)."""
    if force:
        return True

    return _confirm_deletion_prompt()


def delete_migrations_and_force_delete_db(*, force: bool = False) -> None:
    """Delete migration files across project, then drop the DB if deletion happened.

    The heavy lifting is delegated to `_perform_deletion` so this wrapper remains
    small and easy to test.
    """
    project_root = Path(getattr(settings, "BASE_DIR", _find_project_root_candidate()))

    deleted = _perform_deletion(project_root, force=force)
    if deleted:
        force_delete_database()
