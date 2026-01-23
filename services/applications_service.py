from __future__ import annotations

import contextlib
import time

from api.error_codes import (
    APPLICATION_INVALID,
    APPLICATION_NO_JOB,
    APPLICATION_NOT_PENDING,
    INTERNAL_ERROR,
    JOB_NOT_OPEN,
    NOT_AUTHORIZED,
)
from api.errors import ApiError
from api.metrics import (
    APPLICATION_ACCEPT_LATENCY_SECONDS,
    APPLICATION_ACCEPTED,
    APPLICATION_REJECTED,
    safe_inc,
    safe_observe,
)

# Wrap unexpected failures in ApiError so callers (views) only see ApiError
from django.db import transaction

from services.dispatch import emit_background_task
from utilities.app_logging.event_codes import EventCode, LogName
from utilities.app_logging.helpers import get_logger, log_event

# Backwards-compatible alias some callers/tests expect
ApplicationError = ApiError


def accept_application(application: object, user: object) -> None:
    logger = get_logger(__name__)
    start = time.monotonic()

    app_pk = getattr(application, "pk", None)
    if app_pk is None:
        raise ApiError(code=APPLICATION_INVALID, detail="invalid application instance", status=400)

    try:
        with transaction.atomic():
            # Import models lazily to avoid touching Django ORM at module import time
            from applications import models as app_models  # noqa: PLC0415

            locked_app = (
                app_models.Application.objects.select_for_update()  # type: ignore[attr-defined]
                .select_related("job")
                .get(pk=app_pk)
            )

            # authorization: only poster or staff
            job = getattr(locked_app, "job", None)
            poster = getattr(job, "poster", None)
            if not (getattr(user, "is_staff", False) or poster == user):
                raise ApiError(
                    code=NOT_AUTHORIZED,
                    detail="not authorized to accept this application",
                    status=403,
                )

            # only allow from PENDING
            status = getattr(locked_app, "status", None)
            if status is not None and status != app_models.Application.ApplicationStatus.PENDING:
                raise ApiError(
                    code=APPLICATION_NOT_PENDING,
                    detail="application not in pending state",
                    status=409,
                )

            # job must exist and be open
            if job is None:
                raise ApiError(code=APPLICATION_NO_JOB, detail="application has no job", status=400)
            job_status = getattr(job, "status", None)
            if job_status is not None and job_status != job.__class__.JobStatus.OPEN:
                raise ApiError(
                    code=JOB_NOT_OPEN,
                    detail="cannot accept application for non-open job",
                    status=409,
                )

            prev_status = status
            locked_app.status = app_models.Application.ApplicationStatus.ACCEPTED
            locked_app.save()

            # persist audit record
            app_models.ApplicationAction.objects.create(  # type: ignore[attr-defined]
                application=locked_app,
                action=app_models.ACTION_ACCEPT,
                performed_by=user,
                metadata={"from": prev_status, "to": locked_app.status},
            )

            # metrics: non-fatal  # noqa: ERA001
            with contextlib.suppress(Exception):
                safe_inc(APPLICATION_ACCEPTED)
                safe_observe(APPLICATION_ACCEPT_LATENCY_SECONDS, time.monotonic() - start)
    except ApiError:
        raise
    except Exception as exc:
        logger.exception("failed to persist application accept transaction")

        raise ApiError(code=INTERNAL_ERROR, detail="internal server error", status=500) from exc

    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_EXPORT_COMPLETED,
        event="application_accepted",
        application_id=getattr(application, "id", None),
        by_user=getattr(user, "id", None),
    )

    # emit background task on commit
    with contextlib.suppress(Exception):
        emit_background_task(
            "application.accepted",
            {
                "application_id": getattr(application, "id", None),
                "by_user": getattr(user, "id", None),
            },
        )


def reject_application(application: object, user: object) -> None:
    logger = get_logger(__name__)
    start = time.monotonic()

    app_pk = getattr(application, "pk", None)
    if app_pk is None:
        raise ApiError(code=APPLICATION_INVALID, detail="invalid application instance", status=400)

    try:
        with transaction.atomic():
            # Import models lazily to avoid touching Django ORM at module import time
            from applications import models as app_models  # noqa: PLC0415

            locked_app = (
                app_models.Application.objects.select_for_update()  # type: ignore[attr-defined]
                .select_related("job")
                .get(pk=app_pk)
            )

            job = getattr(locked_app, "job", None)
            poster = getattr(job, "poster", None)
            if not (getattr(user, "is_staff", False) or poster == user):
                raise ApiError(
                    code=NOT_AUTHORIZED,
                    detail="not authorized to reject this application",
                    status=403,
                )

            status = getattr(locked_app, "status", None)
            if status is not None and status != app_models.Application.ApplicationStatus.PENDING:
                raise ApiError(
                    code=APPLICATION_NOT_PENDING,
                    detail="application not in pending state",
                    status=409,
                )

            if job is None:
                raise ApiError(code=APPLICATION_NO_JOB, detail="application has no job", status=400)
            job_status = getattr(job, "status", None)
            if job_status is not None and job_status != job.__class__.JobStatus.OPEN:
                raise ApiError(
                    code=JOB_NOT_OPEN,
                    detail="cannot reject application for non-open job",
                    status=409,
                )

            prev_status = status
            locked_app.status = app_models.Application.ApplicationStatus.REJECTED
            locked_app.save()

            app_models.ApplicationAction.objects.create(  # type: ignore[attr-defined]
                application=locked_app,
                action=app_models.ACTION_REJECT,
                performed_by=user,
                metadata={"from": prev_status, "to": locked_app.status},
            )

            with contextlib.suppress(Exception):
                safe_inc(APPLICATION_REJECTED)
                safe_observe(APPLICATION_ACCEPT_LATENCY_SECONDS, time.monotonic() - start)
    except ApiError:
        raise
    except Exception as exc:
        logger.exception("failed to persist application reject transaction")

        raise ApiError(code=INTERNAL_ERROR, detail="internal server error", status=500) from exc

    log_event(
        logger,
        log_name=LogName.AUDIT,
        event_code=EventCode.AUDIT_EXPORT_COMPLETED,
        event="application_rejected",
        application_id=getattr(application, "id", None),
        by_user=getattr(user, "id", None),
    )

    with contextlib.suppress(Exception):
        emit_background_task(
            "application.rejected",
            {
                "application_id": getattr(application, "id", None),
                "by_user": getattr(user, "id", None),
            },
        )


# Backwards-compatible lazy exports: some callers/tests access model symbols
# from this module (e.g., `services.applications_service.Application`). We
# avoid importing `applications.models` at module import time to prevent
# touching the ORM before Django's app registry is ready. Provide a
# module-level `__getattr__` that imports models lazily when accessed.


def __getattr__(name: str) -> object:  # pragma: no cover - runtime laziness
    if name in ("Application", "ApplicationAction", "ACTION_ACCEPT", "ACTION_REJECT"):
        from applications import models as app_models  # noqa: PLC0415

        try:
            return getattr(app_models, name)
        except AttributeError as exc:
            raise AttributeError(f"module 'applications.models' has no attribute '{name}'") from exc
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "__getattr__",
    "accept_application",
    "reject_application",
]
