# Alerts & SLOs (Operational Guidance)

This document describes minimal alerting and dashboard guidance for the API
to ensure the operational team can detect regressions quickly.

Minimal alerts (examples)

- Spike in API endpoint errors (short window)

  - Rule: `increase(api_endpoint_errors_total{env="prod"}[5m]) > 20`
  - Meaning: more than 20 endpoint error events in 5 minutes in production.
  - Severity: warning
  - Runbook: check recent deploys & logs for the endpoint; consider rollback if widespread.

- Spike in throttle hits (short window)

  - Rule: `increase(api_throttle_hits_total{env="prod"}[5m]) > 50`
  - Meaning: more than 50 throttle events in 5 minutes — may indicate abusive clients or misconfiguration.
  - Severity: warning
  - Runbook: inspect top clients, tokens, and throttle scopes; consider rate-limit tuning.

- High p95 latency for application acceptance

  - Rule: `histogram_quantile(0.95, sum(rate(application_accept_latency_seconds_bucket{env="prod"}[5m])) by (le)) > 1.0`
  - Meaning: p95 accept latency > 1.0s in the last 5 minutes.
  - Severity: critical
  - Runbook: check DB slow queries, lock contention, and recent config/deploy changes.

Prometheus rule file

- We include an example PrometheusRule in the repository at `monitoring/kasi-jobs-alerts.yaml`.

Dashboard queries (Grafana)

- API Endpoint Errors (per endpoint)

  - Query: `sum(rate(api_endpoint_errors_total{env="$env"}[5m])) by (endpoint)`
  - Panel: time series; display per-endpoint legend.

- Throttle Hits (per scope)

  - Query: `sum(rate(api_throttle_hits_total{env="$env"}[5m])) by (scope)`

- Accept Latency (p95)

  - Query: `histogram_quantile(0.95, sum(rate(application_accept_latency_seconds_bucket{env="$env"}[5m])) by (le))`

Testing alerts locally

- Steps to simulate and test:
  1. Load `monitoring/kasi-jobs-alerts.yaml` into Prometheus/Prometheus Operator.
  2. Use a metric push or a short script to increment `api_endpoint_errors_total{env="prod",endpoint="application.accept"}` repeatedly.
  3. Confirm alert fires in Alertmanager / Grafana Alerting.

Notes

- Tune thresholds (`>20`, `>50`, `>1.0s`) to match your traffic volume and SLOs. Use rates relative to request volume for better scaling.
- Consider adding per-environment overrides (staging vs prod) and silences for deploy windows.
