import os
import threading
from typing import Any, cast

import pytest
from api.error_codes import APPLICATION_NOT_PENDING
from applications.models import ACTION_ACCEPT, ApplicationAction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from jobs.models import Job
from services import applications_service as svc

EXCEPTIONS_TO_CATCH: tuple[type[Exception], ...] = (ValidationError, IntegrityError)
if hasattr(svc, "ApplicationError"):
    EXCEPTIONS_TO_CATCH = (cast("type[Exception]", svc.ApplicationError), *EXCEPTIONS_TO_CATCH)  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.django_db(transaction=True)
def test_concurrent_accepts_with_db_transactions() -> None:
    """Spawn two threads, each using `transaction.atomic()` to call the accept
    service concurrently. Assert one succeeds and the other fails with
    APPLICATION_NOT_PENDING and only one audit record exists.
    """
    user_model = get_user_model()
    poster = user_model.objects.create_user(
        username="poster_tx", password=os.environ["TEST_USER_PASSWORD"]
    )
    seeker = user_model.objects.create_user(
        username="seeker_tx", password=os.environ["TEST_USER_PASSWORD"]
    )

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="TX Job",
        description="desc",
        location="here",
        estimated_hours=1,
        hourly_rate="20.00",
    )

    application = svc.Application.objects.create(job=job, seeker=seeker)

    results = []

    def worker() -> None:
        try:
            # Each thread opens its own transaction (separate DB connection per thread)
            with transaction.atomic():
                svc.accept_application(application, poster)
            results.append("ok")
        except EXCEPTIONS_TO_CATCH as exc:
            results.append(getattr(exc, "code", type(exc).__name__))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    application.refresh_from_db()

    # final state must be ACCEPTED
    if application.status != application.ApplicationStatus.ACCEPTED:
        raise AssertionError(f"Expected application status ACCEPTED, got {application.status}")

    ok_count = sum(1 for r in results if r == "ok")
    if ok_count != 1:
        raise AssertionError(f"Expected exactly 1 successful accept, got {ok_count}")
    err_codes = [r for r in results if r != "ok"]
    if APPLICATION_NOT_PENDING not in err_codes:
        raise AssertionError(f"Expected error code {APPLICATION_NOT_PENDING} in {err_codes}")

    # exactly one audit record created
    audit_count = (
        cast("Any", ApplicationAction)
        .objects.filter(application=application, action=ACTION_ACCEPT)
        .count()
    )
    if audit_count != 1:
        raise AssertionError(f"Expected 1 audit record, got {audit_count}")
