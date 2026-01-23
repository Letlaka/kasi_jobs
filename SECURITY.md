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
