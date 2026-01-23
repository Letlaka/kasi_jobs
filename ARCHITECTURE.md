# Architecture Guidance

This repository follows a small number of deliberate rules to make the
behaviour of API endpoints predictable, auditable and testable. New
contributors should follow them to avoid subtle bugs and review churn.

Core rules

- Querysets first, permissions second, services always.
  - Views should scope and return querysets; permissions limit visibility.
  - All state-changing work (writes, workflows) must live in the `services/` layer.

- All writes go through services.
  - Service functions receive ORM objects or identifiers and perform
    transactional work, audit records, metrics, and background dispatch.
  - Views and serializers should not contain business logic beyond
    validation and request/response glue.

Service module layout (current)

- Implementation files live under `services/`. The canonical application
  workflow logic is in `services/applications_service.py` (accept/reject,
  audit + metrics + dispatch) — prefer importing that module in views/tests.

Workflow action checklist
When implementing an action (accept, reject, etc.) the *runtime* workflow
must include:

1. Throttle: set a per-action `self.throttle_scope` in the view before calling the service.
2. Authorization: perform object-level authorization in the view (queryset filtering
   and explicit checks) so services can assume caller intent.
3. Service call: call a single service function which is responsible for the transition.
4. Audit record: the service must persist an immutable audit record (e.g. `ApplicationAction`).
5. Metrics: the service should call `safe_inc` / `safe_observe` to record counters and latency.
6. Dispatch: schedule side-effects via `services.dispatch.emit_background_task` (non-blocking).

Tests & enforcement

- Prefer behavioral tests that exercise the view → service → DB flow and assert
  side-effects (audit records, metrics calls, background dispatch interactions).
- Use the provided `WorkflowActionMixin` and tests under `api/tests/` as templates.

Management commands and audit

- The repo includes management commands to export and archive audit/application rows:
  - `applications/management/commands/export_application_audit.py` — export `ApplicationAction` rows as JSON/CSV for subject-access or operational exports.
  - `applications/management/commands/archive_applications.py` — export old `Application` rows and optionally delete them in batches.

These commands are referenced by the operability guidance and should be run with elevated privileges and audited when used in production.

Operational notes

- Keep service functions small and focused; each should have a single responsibility.
- Instrument critical paths with metrics and add Prometheus alerts (see `monitoring/`).

This short contract will keep review surface small: reviewers can check that
the view sets the throttle and permissions and that the service name and
audit/metrics calls exist and are covered by behavioral tests.

## Architecture Guidance (Quick Reference)

This project follows a layered pattern to keep behaviour explicit, testable and auditable.
Keep these rules top-of-mind when adding features or modifying endpoints.

Core principles

- Queryset first, permissions second, services always
  - Views must scope querysets to the requesting user before applying object-level checks.
  - Do not rely on permissions to filter data; filtering belongs in the queryset.
  - Business logic that mutates state belongs in service functions (not in views or serializers).

Error handling contract

- Service layer raises `ApiError` only:
  - Services should raise `ApiError` for expected business failures (validation, permission, state transitions).
  - Unexpected exceptions should be logged and wrapped in an `ApiError` with an `internal_error` code before propagating to views.

- Views translate `ApiError` to HTTP responses and must not raise domain errors directly:
  - Views should catch `ApiError` from services and return the appropriate HTTP payload/status using `ApiError.to_payload()`.
  - Do not raise raw exceptions or DRF domain errors from views for business logic; keep views as adapters.

Required practices (developer checklist)

- All writes go through services
  - Create, update and state transitions must be implemented as functions in `services/`.
  - Services are responsible for transactions, validation, audit events and metrics.
  - Views call services and convert service errors (e.g. `ApiError`) to HTTP responses.

- All custom actions must paginate
  - Any view action that can return a collection (e.g. `GET /jobs/{id}/applications/`) must explicitly paginate results.
  - Use the viewset's `paginate_queryset` and `get_paginated_response` helpers.

- All workflow actions must emit audit + metrics
  - Service-layer workflow transitions (accept/reject/etc.) must:
    - Persist an immutable audit record (e.g. `ApplicationAction`).
    - Increment counters (e.g. `APPLICATION_ACCEPTED`) and record latency histograms.
    - Emit non-blocking background tasks with `services.dispatch.emit_background_task` where needed.

Why these rules

- Centralising writes in the service layer prevents business logic duplication and makes it easier to add retries, compensating actions, or observability.
- Pagination prevents accidental full-table reads and makes endpoints safe at scale.
- Audit + metrics ensure incidents are diagnosable and that behaviour changes are visible without reading logs.

Quick examples

- View -> Service call (good):

  - View validates request, scopes queryset, authorizes, then calls `services.applications.accept_application(application, user)`.
  - Service opens a transaction, `select_for_update()` the row, enforces invariants, writes audit record, updates metrics, returns/raises `ApiError` on business failures.

- Bad pattern (avoid):
  - Implementing complex accept/reject logic inside a view or serializer and saving models directly. This makes it easy to forget audit/metrics and harder to test.

Enforcement suggestions

- Code review checklist: require reviewers to confirm service usage, pagination, and metrics/audit presence for new workflows.
- Add unit tests that assert services create audit records and increment metrics counters.
- Add a short static check (optional) to flag uses of model `save()` inside `api/views.py` without calling services.

Where to look for examples

- Service implementations: `services/applications.py` (accept / reject)
- Dispatch + background tasks: `services/dispatch.py`
- Audit models: `applications/models.py` (`ApplicationAction`)
- Metrics helpers: `api/metrics.py`
