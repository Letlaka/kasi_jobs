from unittest.mock import patch

import pytest
from django.core.management.base import CommandError

from utilities.db.pg_backup_utils import run_subprocess, validate_subprocess_command


def test_validate_rejects_empty_or_nonlist():
    with pytest.raises(CommandError):
        validate_subprocess_command([])
    with pytest.raises(CommandError):
        validate_subprocess_command("ls -la")  # type: ignore[arg-type]


def test_validate_rejects_forbidden_characters():
    with pytest.raises(CommandError):
        validate_subprocess_command(["/bin/sh", "-c", "rm -rf /; echo hi"])  # semicolon


def test_validate_allows_simple_command():
    # simple executable name and safe args
    validate_subprocess_command(["pg_dump", "-h", "127.0.0.1"])  # should not raise


@patch("subprocess.run")
def test_run_subprocess_invokes_run_when_safe(mock_run):
    # Should call subprocess.run when the command is safe
    run_subprocess(["pg_dump", "-h", "127.0.0.1"], env={})
    mock_run.assert_called_once()


@patch("subprocess.run")
def test_run_subprocess_raises_on_forbidden(mock_run):
    with pytest.raises(CommandError):
        run_subprocess(["/bin/sh", "-c", "echo hi; rm -rf /"], env={})
    mock_run.assert_not_called()
