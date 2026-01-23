# kasi-jobs

Lightweight job application API (Django + DRF) with a service-layer workflow,
audit records, and operational observability.

Quick start (developer)

- Create and activate virtualenv:

```powershell
python -m venv .venv
& ./.venv/Scripts/Activate.ps1
pip install -e .[dev]
```

- Run tests (pytest):

```powershell
pytest -q
```

- Static checks:

```powershell
uv run mypy .
uv run ruff check . --fix --show-fixes
```

Notes about running ruff and mypy in this repo:
- Use the project launcher `uv` (UVicorn runner wrapper) when available: `uv run ruff ...` or `uv run mypy ...`.

Management commands (examples)

- Archive old applications (dry-run first):

```powershell
python manage.py archive_applications --days 365 --batch-size 1000 --dry-run
```

- Export per-application audit rows (JSON/CSV):

```powershell
python manage.py export_application_audit <application_id> --format json
```

Where to look

- API views and tests: `api/` and `api/tests/`
- Service layer (business logic): `services/` (e.g. `services/applications_service.py`)
- Audit models: `applications/models.py` (`ApplicationAction`)
- Management commands: `applications/management/commands/`
- Operability guidance: `OPERABILITY.md`
- Audit retention policy: `AUDIT_RETENTION_POLICY.md`
- Security guidance: `SECURITY.md`

Conventions

- Querysets first, permissions second, services always — keep views thin and put write logic in `services/`.
- All workflow actions must persist audit records and call `safe_inc` / `safe_observe` for metrics.

If you want me to update other docs (SECURITY.md, ARCHITECTURE.md, OPERABILITY.md) to reflect recent code changes (new commands, metrics, tests), I can scan and apply targeted edits next.

