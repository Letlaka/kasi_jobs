"""Email validator."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils.translation import gettext_lazy as _

from utilities.app_logging import get_logger, log_event
from utilities.app_logging.event_codes import EventCode, LogName


def validate_email_address(
    email: str,
    *,
    whitelist_domains: list[str] | None = None,
    blacklist_domains: list[str] | None = None,
) -> None:
    """Validate email address using Django's EmailValidator.

    Optionally restrict by whitelist or blacklist domains.
    """
    logger = get_logger(__name__)
    if email is None or str(email).strip() == "":
        log_event(
            logger,
            log_name=LogName.SECURITY,
            event_code=EventCode.AUDIT_VALIDATION_EMAIL_FAILED,
            event="email_missing",
            field="email",
        )
        raise ValidationError(_("Email is required."), code="required")
    validator = EmailValidator(message=_("Enter a valid email address."))
    validator(email)

    # Optional domain restrictions
    if whitelist_domains or blacklist_domains:
        domain = str(email).rsplit("@", 1)[-1].lower()
        lower_whitelist = [d.lower() for d in whitelist_domains] if whitelist_domains else []
        lower_blacklist = [d.lower() for d in blacklist_domains] if blacklist_domains else []
        if lower_whitelist and domain not in lower_whitelist:
            log_event(
                logger,
                log_name=LogName.SECURITY,
                event_code=EventCode.AUDIT_VALIDATION_EMAIL_FAILED,
                event="email_domain_not_whitelisted",
                field="email",
                domain=domain,
            )
            raise ValidationError(_("Email domain not allowed."), code="invalid_domain")
        if lower_blacklist and domain in lower_blacklist:
            log_event(
                logger,
                log_name=LogName.SECURITY,
                event_code=EventCode.AUDIT_VALIDATION_EMAIL_FAILED,
                event="email_domain_blacklisted",
                field="email",
                domain=domain,
            )
            raise ValidationError(_("Email domain not allowed."), code="invalid_domain")
