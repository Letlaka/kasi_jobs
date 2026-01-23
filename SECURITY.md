# Queryset first, permissions second, services always

Short guidance for developers contributing API endpoints:

- Ensure queryset scoping (filter by request.user / owner) before relying on permissions.
- Apply permission checks (object- and view-level) as a second line of defence.
- Put workflow/business rules in service layer functions and persist audit events there.

Implementation notes (current repo)

- Canonical service implementations live under `services/` — e.g. `services/applications_service.py`.
- Tests that assert security and behavioral contracts are under `api/tests/` (behavioral, throttle, and workflow tests).
- Management commands that touch audit/export/archival are in `applications/management/commands/` (e.g. `export_application_audit`, `archive_applications`).

This helps avoid accidental data exposure and keeps business logic centralized.

## Dependency scanning and weekly audits

We run automated dependency scans to detect known vulnerabilities in Python packages.

- Dependabot: configured to check for updates weekly and open PRs for outdated dependencies. See `.github/dependabot.yml`.
- GitHub Actions: a scheduled workflow (`.github/workflows/dependency-audit.yml`) runs `pip-audit` and `safety` and uploads JSON reports as artifacts.

Operational notes:

- Ensure `pyproject.toml` or `requirements.txt` accurately reflects pinned dependencies so audit tools can reproduce install environments.
- If you rely on ClamAV, `python-magic`, or other optional runtime libraries, document them in deployment manifests and install them on your CI/CD runners when required.
- Triage any Dependabot or audit findings promptly; create issues for high/critical vulnerabilities and link to remediation PRs.
