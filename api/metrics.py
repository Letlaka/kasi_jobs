"""Prometheus metrics and helpers for API observability.

Defines lightweight counters/histograms used by the API. Guards imports
so the code continues to work when prometheus_client isn't installed
(e.g. in lightweight dev environments).
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

_ENV = getattr(settings, "ENVIRONMENT", None) or getattr(settings, "ENV", "local")

APPLICATIONS_CREATED: Any | None = None
APPLICATION_ACCEPTED: Any | None = None
APPLICATION_REJECTED: Any | None = None
API_ENDPOINT_ERRORS: Any | None = None
APPLICATION_ACCEPT_LATENCY_SECONDS: Any | None = None
THROTTLE_HITS: Any | None = None

try:  # pragma: no cover - metrics optional in tests
    from prometheus_client import Counter, Histogram

    APPLICATIONS_CREATED = Counter(
        "applications_created_total",
        "Total number of applications created",
        ["env"],
    ).labels(_ENV)

    APPLICATION_ACCEPTED = Counter(
        "application_accept_total",
        "Total number of application accept operations",
        ["env"],
    ).labels(_ENV)

    APPLICATION_REJECTED = Counter(
        "application_reject_total",
        "Total number of application reject operations",
        ["env"],
    ).labels(_ENV)

    API_ENDPOINT_ERRORS = Counter(
        "api_endpoint_errors_total",
        "Total number of errors per endpoint",
        ["env", "endpoint", "method", "status"],
    )

    THROTTLE_HITS = Counter(
        "api_throttle_hits_total",
        "Total number of throttle hits",
        ["env", "scope"],
    )

    APPLICATION_ACCEPT_LATENCY_SECONDS = Histogram(
        "application_accept_latency_seconds",
        "Latency for application accept operations",
        ["env"],
    ).labels(_ENV)
except (ImportError, RuntimeError):  # pragma: no cover
    APPLICATIONS_CREATED = APPLICATION_ACCEPTED = APPLICATION_REJECTED = API_ENDPOINT_ERRORS = (
        APPLICATION_ACCEPT_LATENCY_SECONDS
    ) = THROTTLE_HITS = None


def safe_inc(counter: Any | None, *labels: object) -> None:
    """Increment a counter if available.

    Labels may be passed when the metric wasn't pre-labeled.
    """
    if counter is None:
        return
    try:
        # metrics objects are typed as Any above so mypy won't complain
        if labels:
            counter.labels(*labels).inc()
        else:
            counter.inc()
    except Exception:
        # metric failures must not impact application logic
        return


def safe_observe(hist: Any | None, value: float) -> None:
    if hist is None:
        return
    try:
        hist.observe(value)
    except Exception:
        return
