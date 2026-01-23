import os

import pytest
from applications.models import Application
from django.contrib.auth import get_user_model
from django.db import transaction
from jobs.models import Job
from services import applications_service as svc, dispatch


@pytest.mark.django_db
def test_emit_background_task_invokes_receiver_after_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_model = get_user_model()
    test_password = os.environ.get("TEST_USER_PASSWORD", "pw")
    poster = user_model.objects.create_user(username="poster_bg", password=test_password)
    seeker = user_model.objects.create_user(username="seeker_bg", password=test_password)

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="BG Job",
        description="desc",
        location="here",
        estimated_hours=1,
        hourly_rate="10.00",
    )

    application = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    events: list[dict] = []

    def receiver(_sender: object, **kwargs: object) -> None:
        events.append(dict(kwargs))

    # make transaction.on_commit call callbacks immediately in this test
    monkeypatch.setattr(transaction, "on_commit", lambda func: func())

    # connect receiver
    dispatch.background_task_requested.connect(receiver)
    try:
        # call the service which schedules emit_background_task on commit
        svc.accept_application(application, poster)

        # after the service returns, the on_commit callback should have fired
        if len(events) < 1:
            raise AssertionError("No events emitted on commit")
        ev = events[0]
        if ev.get("name") != "application.accepted":
            raise AssertionError(f"Unexpected event name: {ev.get('name')!r}")
        if not isinstance(ev.get("payload"), dict):
            raise AssertionError("Event payload is not a dict")
        if ev["payload"].get("application_id") != application.pk:
            raise AssertionError(
                f"Payload application_id {ev['payload'].get('application_id')!r}"
                 "does not match application.pk {application.pk!r}"
            )
    finally:
        dispatch.background_task_requested.disconnect(receiver)
