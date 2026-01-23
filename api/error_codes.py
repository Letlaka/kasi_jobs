"""Stable error code constants returned by the API.

Clients should rely on these stable `code` strings for programmatic
decisions. Keep values lower_snake_case for readability.
"""

APPLICATION_INVALID = "application_invalid"
APPLICATION_NOT_PENDING = "application_not_pending"
APPLICATION_NO_JOB = "application_no_job"
APPLICATION_ALREADY_PROCESSED = "application_already_processed"
JOB_NOT_OPEN = "job_not_open"
NOT_AUTHORIZED = "not_authorized"
INVALID_REQUEST = "invalid_request"
INTERNAL_ERROR = "internal_error"

__all__ = [
    "APPLICATION_ALREADY_PROCESSED",
    "APPLICATION_INVALID",
    "APPLICATION_NOT_PENDING",
    "APPLICATION_NO_JOB",
    "INTERNAL_ERROR",
    "INVALID_REQUEST",
    "JOB_NOT_OPEN",
    "NOT_AUTHORIZED",
]
