"""Centralized throttle scope constants.

Keep throttle scope names here to avoid scattered string literals and
reduce risk of misconfiguration or typos across the codebase.
"""

# Basic scopes used by views
THROTTLE_JOB = "job"
THROTTLE_APPLICATION = "application"

# Action-specific scopes
THROTTLE_APPLICATION_ACCEPT = "application_accept"
THROTTLE_APPLICATION_REJECT = "application_reject"

# Export a list for any automated registration or documentation tooling
ALL_THROTTLE_SCOPES = (
    THROTTLE_JOB,
    THROTTLE_APPLICATION,
    THROTTLE_APPLICATION_ACCEPT,
    THROTTLE_APPLICATION_REJECT,
)
