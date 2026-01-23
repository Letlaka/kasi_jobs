import threading

import pytest


@pytest.mark.django_db(transaction=True)
def test_concurrent_accepts_only_one_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.error_codes import APPLICATION_NOT_PENDING
    from applications.models import ACTION_ACCEPT, ApplicationAction
    from django.contrib.auth import get_user_model
    from jobs.models import Job
    from services import applications_service as svc

    User = get_user_model()
    poster = User.objects.create_user(username="poster_conc", password="pw")
    seeker = User.objects.create_user(username="seeker_conc", password="pw")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Concurrent Job",
        description="desc",
        location="here",
        estimated_hours=1,
        hourly_rate="15.00",
    )

    application = svc.Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    # track metric helper calls
    calls = {"inc": 0, "obs": 0}

    def fake_inc(counter: object, *labels: object) -> None:
        calls["inc"] += 1

    def fake_obs(hist: object, value: object) -> None:
        calls["obs"] += 1

    monkeypatch.setattr(svc, "safe_inc", fake_inc)
    monkeypatch.setattr(svc, "safe_observe", fake_obs)

    results = []

    def worker() -> None:
        try:
            svc.accept_application(application, poster)
            results.append("ok")
        except Exception as exc:  # capture ApiError or other
            code = getattr(exc, "code", None)
            results.append(code or type(exc).__name__)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    application.refresh_from_db()

    # final state must be ACCEPTED
    assert application.status == application.ApplicationStatus.ACCEPTED

    # exactly one successful accept and one ApiError with APPLICATION_NOT_PENDING
    ok_count = sum(1 for r in results if r == "ok")
    assert ok_count == 1

    err_codes = [r for r in results if r != "ok"]
    assert err_codes, "expected one error result"
    assert APPLICATION_NOT_PENDING in err_codes

    # audit record count must be exactly 1
    assert (
        ApplicationAction.objects.filter(application=application, action=ACTION_ACCEPT).count() == 1  # type: ignore[attr-defined]
    )
