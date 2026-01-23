"""API error types and helpers.

Raise `ApiError` from service/business code to return a stable error
shape to API clients. Views may catch `ApiError` and render the
following JSON shape:

    {"code": "application_not_pending", "detail": "human message"}

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ApiError(Exception):
    code: str
    detail: str
    status: int = 400

    def to_payload(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail}


def as_response_dict(exc: ApiError) -> dict[str, Any]:
    return exc.to_payload()


__all__ = ["ApiError", "as_response_dict"]
