import json
import logging

from django.db import connections
from django.db.utils import OperationalError
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

logger = logging.getLogger("utilities.audit")


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
        status = 200 if db_ok else 503
        return JsonResponse({"database": "ok" if db_ok else "unavailable"}, status=status)

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
        logger.warning("CSP violation report", extra={"csp_report": payload})
        return JsonResponse({}, status=204)

    # allow GET for quick smoke tests (returns simple JSON)
    def get(self, _request: HttpRequest) -> JsonResponse:
        return JsonResponse({"status": "ok"})
