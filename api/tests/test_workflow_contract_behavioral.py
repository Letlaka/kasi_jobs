import pytest


@pytest.mark.django_db
def test_accept_application_updates_db_and_calls_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    from applications.models import ACTION_ACCEPT, Application, ApplicationAction
    from django.contrib.auth import get_user_model
    from jobs.models import Job
    from services import applications_service as svc

    User = get_user_model()
    poster = User.objects.create_user(username="poster", password="pw")
    seeker = User.objects.create_user(username="seeker", password="pw")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Test Job",
        description="desc",
        location="here",
        estimated_hours=1,
        hourly_rate="10.00",
    )

    application = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    calls = {"inc": 0, "obs": 0}

    def fake_inc(counter: object, *labels: object) -> None:
        calls["inc"] += 1

    def fake_obs(hist: object, value: object) -> None:
        # record that we observed a latency-like float
        assert isinstance(value, float)
        calls["obs"] += 1

    # patch the helpers that were bound into the service module
    monkeypatch.setattr(svc, "safe_inc", fake_inc)
    monkeypatch.setattr(svc, "safe_observe", fake_obs)

    # call the service as the poster (authorized)
    svc.accept_application(application, poster)

    application.refresh_from_db()
    assert application.status == Application.ApplicationStatus.ACCEPTED

    # audit record created
    assert ApplicationAction.objects.filter(application=application, action=ACTION_ACCEPT).exists()  # type: ignore[attr-defined]

    # metrics helpers were invoked
    assert calls["inc"] >= 1
    assert calls["obs"] >= 1


@pytest.mark.django_db
def test_reject_application_updates_db_and_calls_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    from applications.models import ACTION_REJECT, Application, ApplicationAction
    from django.contrib.auth import get_user_model
    from jobs.models import Job
    from services import applications_service as svc

    User = get_user_model()
    poster = User.objects.create_user(username="poster2", password="pw")
    seeker = User.objects.create_user(username="seeker2", password="pw")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Test Job 2",
        description="desc",
        location="there",
        estimated_hours=1,
        hourly_rate="12.00",
    )

    application = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    calls = {"inc": 0, "obs": 0}

    def fake_inc(counter: object, *labels: object) -> None:
        calls["inc"] += 1

    def fake_obs(hist: object, value: object) -> None:
        assert isinstance(value, float)
        calls["obs"] += 1

    monkeypatch.setattr(svc, "safe_inc", fake_inc)
    monkeypatch.setattr(svc, "safe_observe", fake_obs)

    svc.reject_application(application, poster)

    application.refresh_from_db()
    assert application.status == Application.ApplicationStatus.REJECTED
    assert ApplicationAction.objects.filter(application=application, action=ACTION_REJECT).exists()  # type: ignore[attr-defined]
    assert calls["inc"] >= 1
    assert calls["obs"] >= 1
