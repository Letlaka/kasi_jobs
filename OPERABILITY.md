# Operability: Alerts & Dashboard Contract

This document defines three basic alerts and a minimal dashboard contract to make existing metrics operational.

Metrics (existing)

- `api_endpoint_errors_total{endpoint,method,env}` — counter incremented when a handler returns an ApiError.
- `api_throttle_hits_total{endpoint,env,scope}` — counter for throttle events.
- `application_accept_latency_seconds_bucket{le,env}` — histogram from accept/reject service call.
- `application_accept_latency_seconds_count` / `_sum` — histogram helpers.

Notes (current repo)

- Management commands: `archive_applications` and `export_application_audit` live under `applications/management/commands/` and are referenced in the Archiving and Audit sections.
- Background dispatch uses the `services.dispatch.background_task_requested` signal; the health endpoint reports `background_task_receivers` in production.

Goals

- Detect spikes in endpoint errors and throttles quickly.
- Alert on latency regressions for the accept action (p95).
- Provide a dashboard-contract so panels are stable and documented.

Basic Alerting Rules (examples — tune thresholds for your traffic)

1) Spike in api endpoint errors (short window)

- Purpose: catch sudden error storms from deploys or regressions.
- Example rule (Prometheus `PrometheusRule`):

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: kasi-jobs-basic-alerts
  labels:
    role: alert-rules
spec:
  groups:
  - name: api-error-alerts
    rules:
    - alert: ApiEndpointErrorsSpike
      expr: increase(api_endpoint_errors_total[5m]) > 5
      for: 2m
      labels:
        severity: warning
      annotations:
        summary: "Spike in API endpoint errors ({{ $labels.endpoint }})"
        description: "api_endpoint_errors_total increased by more than 5 in 5m. Check recent deploys and logs."
```

Notes: Replace `> 5` with a rate relative to request volume if you have `api_requests_total` available, e.g. `rate(api_endpoint_errors_total[5m]) / rate(api_requests_total[5m]) > 0.01` for >1% error rate.

1) Spike in throttle hits

- Purpose: detect when clients are being throttled (possible abusive traffic, broken clients, or misconfigured rate limits).

```yaml
  - name: throttle-alerts
    rules:
    - alert: ApiThrottleHitsSpike
      expr: increase(api_throttle_hits_total[5m]) > 10
      for: 2m
      labels:
        severity: warning
      annotations:
        summary: "Spike in throttle hits"
        description: "api_throttle_hits_total increased by more than 10 in 5m. Investigate throttled endpoints and clients."
```

1) p95 accept latency regression

- Purpose: detect performance regressions in the accept workflow.
- Use histogram quantile over a short window.

```yaml
  - name: latency-alerts
    rules:
    - alert: AcceptP95LatencyHigh
      expr: |
        histogram_quantile(0.95, sum(rate(application_accept_latency_seconds_bucket[5m])) by (le)) > 1.0
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "High p95 latency for application acceptance"
        description: "p95 of application_accept_latency_seconds over 5m is > 1.0s. Investigate service and DB latency."
```

Notes: Choose threshold (here `1.0s`) appropriate for your latency SLO.

Dashboard Contract (minimal)

- Panel: `API Endpoint Errors` — query: `sum(rate(api_endpoint_errors_total[5m])) by (endpoint)`
- Panel: `Throttle Hits` — query: `sum(rate(api_throttle_hits_total[5m])) by (endpoint)`
- Panel: `Accept Latency (p95)` — query: `histogram_quantile(0.95, sum(rate(application_accept_latency_seconds_bucket[5m])) by (le))`

Runbook (short)

- ApiEndpointErrorsSpike
  - Check recent deploys and error logs for the endpoint in the last 10 minutes.
  - If errors are widespread and new, consider rolling back the last deploy.
  - If errors due to third-party failures, escalate to infra and vendor.
- ApiThrottleHitsSpike
  - Inspect top client IPs or tokens (if labelled) causing the hits.
  - If legitimate traffic surge, consider increasing limits or scaling.
- AcceptP95LatencyHigh
  - Check DB slow queries, lock contention, and service CPU/memory.
  - Correlate with deployment events and recent config changes.

Slow Query Detection for `/jobs/{id}/applications/`

- Purpose: detect slow queries when listing applications for a job (joins, large poster history, or missing indexes).
- Prometheus / Alert example (use your DB exporter metrics; this uses a generic `pg_stat_statements` gauge exposed as `pg_stat_statements_max_time` or similar):

```yaml
  - name: db-slow-queries
    rules:
    - alert: JobApplicationsSlowQuery
      expr: increase(pg_stat_statements_total_time_seconds{query~"applications.*JOIN.*jobs"}[5m]) > 1.0
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "Slow queries touching applications/jobs detected"
        description: "Queries for listing applications on jobs have accumulated >1s total execution time in 5m. Investigate indexes and query plans."
```

Notes:

- Replace the `expr` with a query suitable for your DB exporter (e.g., `pg_stat_statements` metrics or slow query logs parsed into Prometheus). The intent is to surface sustained slow query time for queries that join `applications` and `jobs`.
- When alerted, capture an `EXPLAIN (ANALYZE, BUFFERS)` for the slow query and look for sequential scans, large sorts, or repeated index scans. Consider adding or tuning indexes (e.g., `apps_job_applied_at_idx`) or switching to cursor pagination.

Archiving old applications (operational mitigation)

- Rationale: some posters may accumulate very large numbers of historical applications. Archiving older records reduces active table size and improves query plans for recent data.
- Strategy (non-breaking):
  - Export older applications to a compressed JSON/NDJSON file and then delete them from the primary table in a transactional batch.
  - Keep archives in object storage (S3) or in a separate archival database/table that is queried rarely.

- Example management command exists in the repo: `applications/management/commands/archive_applications.py`. It:
  - Exports applications older than a configurable threshold (days) to a JSON file.
  - Optionally uploads to S3 (if configured) and deletes exported rows in a transaction.
  - Operates in batches to avoid long-lived transactions and reduce lock contention.

- Runbook for archiving:
  
 1. Run the management command with a safe `--days` threshold and `--dry-run` to preview counts and file names.
 2. Inspect the exported file and optionally upload to cold storage.
 3. Re-run without `--dry-run` to delete archived rows. Monitor DB locks and slow queries during the operation.

Example command:

```powershell
& ./.venv/Scripts/Activate.ps1
python manage.py archive_applications --days 365 --batch-size 1000 --dry-run
```

Contact: DBA or on-call when planning bulk archive runs during low-traffic windows.

Background dispatch receivers (expected)

- `celery` worker: a receiver that forwards `background_task_requested` signals to a Celery task queue.
- `webhook-bridge` service: optional bridge that forwards events to external webhook sinks.
- Other integrators: any process that registers a receiver on `services.dispatch.background_task_requested`.

Validation: the health endpoint `/health/` reports `background_task_receivers` in production and the service startup will log an error if none are registered.
