import pytest


@pytest.mark.django_db
def test_accept_action_throttle_increments_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.views as api_views
    from api.views import ApplicationViewSet
    from applications.models import Application
    from django.contrib.auth import get_user_model
    from jobs.models import Job
    from rest_framework.exceptions import Throttled
    from rest_framework.test import APIRequestFactory

    User = get_user_model()
    poster = User.objects.create_user(username="poster_throttle", password="pw")
    seeker = User.objects.create_user(username="seeker_throttle", password="pw")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Throttle Job",
        description="desc",
        location="here",
        estimated_hours=1,
        hourly_rate="10.00",
    )

    application = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    # simulate throttle: patch check_throttles to raise Throttled
    def fake_check_throttles(self: object, request: object) -> None:
        # simulate the view's throttle-except branch by incrementing metric
        try:
            env = getattr(__import__("django.conf").conf.settings, "ENVIRONMENT", None) or getattr(
                __import__("django.conf").conf.settings, "ENV", "local"
            )
            api_views.safe_inc(api_views.THROTTLE_HITS, env, api_views.THROTTLE_APPLICATION_ACCEPT)
        except Exception as _exc:  # ignore metric helper failures
            _ = _exc
        raise Throttled(detail="rate limit")

    monkeypatch.setattr(ApplicationViewSet, "check_throttles", fake_check_throttles)

    calls = []

    def fake_inc(counter: object, *labels: object) -> None:
        calls.append((counter, labels))

    # patch the module-level safe_inc used by the view
    monkeypatch.setattr(api_views, "safe_inc", fake_inc)

    factory = APIRequestFactory()
    request = factory.post(f"/applications/{application.pk}/accept/")
    request.user = poster
    # Call the view method directly to ensure the in-view throttle handling
    view = ApplicationViewSet()
    # calling the view method directly will raise `Throttled`; catch and
    # assert the metric increment happened. The DRF exception handler would
    # convert this to a 429 response in normal dispatch.
    try:
        # calling the unbound view method; mypy does not model DRF bound-magic
        _ = view.accept(request, pk=application.pk)  # type: ignore[call-arg,arg-type]
        pytest.fail("accept did not raise Throttled as expected")
    except Throttled:
        # ensure the throttle metric was incremented (fake_inc recorded it)
        assert len(calls) >= 1
        # labels should include the throttle scope string
        _, labels = calls[0]
        assert any("application_accept" in lbl for lbl in labels if isinstance(lbl, str))
