import json
import logging

from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from services.dispatch import count_background_receivers

from utilities.validators import sanitize_text_field

logger = logging.getLogger("utilities.audit")


def _sanitize_payload(obj: object) -> object:
    """Recursively sanitize string values in the payload to avoid logging PII."""
    if isinstance(obj, str):
        return sanitize_text_field(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_payload(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_payload(v) for v in obj]
    return obj


class IndexView(TemplateView):
    title = "Contacts"
    template_name = "core/index.html"


class HealthView(View):
    """Basic health check for the service implemented as a class-based view.

    Returns JSON with database connectivity status. Prometheus or external
    monitoring can scrape `/metrics/` for metrics and call `/health/` for
    liveness/readiness.
    """

    def _db_ok(self) -> bool:
        db_conn = connections["default"]
        try:
            # run a very simple query to validate DB connectivity
            c = db_conn.cursor()
            c.execute("SELECT 1")
            return True
        except OperationalError:
            return False

    def get(self, _request: HttpRequest) -> JsonResponse:
        db_ok = self._db_ok()
        # In production, ensure at least one background task receiver is registered.
        receivers_ok = True
        env = getattr(settings, "ENVIRONMENT", None) or getattr(settings, "ENV", "local")
        try:
            if env == "production":
                receivers_ok = count_background_receivers() > 0
        except (ImportError, AttributeError, RuntimeError) as err:
            logger.exception("error checking background task receivers: %s", err)
            receivers_ok = False

        status_code = 200 if (db_ok and receivers_ok) else 503
        payload = {"database": "ok" if db_ok else "unavailable"}
        if env == "production":
            payload["background_task_receivers"] = "ok" if receivers_ok else "none_registered"
        return JsonResponse(payload, status=status_code)

    # Allow HEAD requests to act like GET for health checks
    head = get


@method_decorator(csrf_exempt, name="dispatch")
class CSPReportView(View):
    """Endpoint to receive CSP violation reports from browsers.

    Browsers will POST JSON bodies with violation details. We log them
    at warning level for ops/forensics and return 204 No Content.
    """

    def post(self, request: HttpRequest) -> JsonResponse:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"raw": request.body.decode("utf-8", "ignore")}
        safe_payload = _sanitize_payload(payload)
        logger.warning("CSP violation report", extra={"csp_report": safe_payload})
        return JsonResponse({}, status=204)

    # allow GET for quick smoke tests (returns simple JSON)
    def get(self, _request: HttpRequest) -> JsonResponse:
        return JsonResponse({"status": "ok"})
