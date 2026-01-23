from __future__ import annotations

import logging
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from api.error_codes import INTERNAL_ERROR
from api.errors import ApiError

logger = logging.getLogger(__name__)


class ApiExceptionMiddleware:
    """Convert ApiError and uncaught exceptions to a standardized JSON payload.

    - If an `ApiError` is raised, return its payload and status.
    - For other exceptions, log and return a 500 with `internal_error` code.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            return self.get_response(request)
        except ApiError as exc:
            return JsonResponse(exc.to_payload(), status=getattr(exc, "status", 400))
        except Exception as exc:  # pragma: no cover - runtime
            logger.exception("Unhandled exception in request: %s", exc)
            return JsonResponse(
                {"code": INTERNAL_ERROR, "detail": "internal server error"}, status=500
            )
