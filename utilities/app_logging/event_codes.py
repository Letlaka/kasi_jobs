from __future__ import annotations

from enum import Enum, IntEnum
from typing import Final


class LogName(str, Enum):
    """Logical log channels, similar to Windows Event Logs."""

    APPLICATION = "Application"
    SECURITY = "Security"
    SYSTEM = "System"
    AUDIT = "Audit"  # For cross-cutting / whole-system events


APP_START = 1000
APP_END = 1999
SEC_START = 2000
SEC_END = 2999
SYS_START = 3000
SYS_END = 3999
AUDIT_START = 9000
AUDIT_END = 9999


class EventCode(IntEnum):
    """
    Numeric event IDs, grouped by category (Windows-style):

    1xxx = Application
    2xxx = Security
    3xxx = System
    9xxx = Audit / Cross-cutting
    """

    # --- Application (1xxx) ---
    APPLICATION_DB_CREATE_REQUESTED = 1000
    APPLICATION_DB_CREATED = 1001
    APPLICATION_DB_ALREADY_EXISTS = 1002

    # --- Security (2xxx) ---
    SECURITY_LOGIN_SUCCESS = 2000
    SECURITY_LOGIN_FAILED = 2001
    SECURITY_PERMISSION_DENIED = 2002
    SECURITY_LOGOUT = 2003
    SECURITY_SIGNUP = 2004
    SECURITY_PASSWORD_CHANGED = 2005
    SECURITY_PASSWORD_RESET = 2006
    SECURITY_PASSWORD_EXPIRED = 2007
    SECURITY_ACCOUNT_LOCKED = 2008
    SECURITY_ACCOUNT_UNLOCKED = 2009
    SECURITY_ACCOUNT_UPDATED = 2010

    # --- System (3xxx) ---
    SYSTEM_STARTUP = 3000
    SYSTEM_SHUTDOWN = 3001
    SYSTEM_ERROR = 3002

    # --- Audit / Cross-cutting (9xxx) ---
    AUDIT_EXPORT_STARTED = 9000
    AUDIT_EXPORT_COMPLETED = 9001
    AUDIT_CONFIG_CHANGED = 9002
    # --- Validation / PII (9xxx) ---
    AUDIT_VALIDATION_PHONE_FAILED = 9003
    AUDIT_VALIDATION_EMAIL_FAILED = 9004
    AUDIT_VALIDATION_SA_ID_FAILED = 9005
    AUDIT_VALIDATION_SANITIZE_TRUNCATED = 9006
    AUDIT_VALIDATION_DECIMAL_FAILED = 9007
    AUDIT_CONSENT_MISSING = 9008


# Map event_name -> EventCode for fast lookup
EVENT_NAME_TO_CODE: Final[dict[str, EventCode]] = {code.name: code for code in EventCode}


def derive_log_name_from_event_code(event_code: int) -> str:
    """
    Derive Windows-style 'Log Name' from numeric event_id.
    """

    if APP_START <= event_code < APP_END:
        return "Application"
    if SEC_START <= event_code < SEC_END:
        return "Security"
    if SYS_START <= event_code < SYS_END:
        return "System"
    if AUDIT_START <= event_code < AUDIT_END:
        return "Audit"
    return "Application"
