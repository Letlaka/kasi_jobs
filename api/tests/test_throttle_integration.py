import pytest


@pytest.mark.django_db
def test_accept_action_throttle_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.views as api_views
    from api.views import ApplicationViewSet
    from applications.models import Application
    from django.contrib.auth import get_user_model
    from jobs.models import Job
    from rest_framework.test import APIRequestFactory

    User = get_user_model()
    poster = User.objects.create_user(username="poster_integ", password="pw")
    seeker = User.objects.create_user(username="seeker_integ", password="pw")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Integ Job",
        description="desc",
        location="here",
        estimated_hours=1,
        hourly_rate="10.00",
    )

    application = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    # a throttle class that always denies requests
    class AlwaysThrottle:
        def allow_request(self, _request: object, _view: object) -> bool:
            return False

        def wait(self) -> None:
            return None

    # install the throttle on the viewset class before building the view
    monkeypatch.setattr(ApplicationViewSet, "throttle_classes", (AlwaysThrottle,))

    # avoid DRF's View.initial early throttle check so the in-view handler runs
    def _initial(_self: object, _request: object, *_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(ApplicationViewSet, "initial", _initial)

    calls = []

    def fake_inc(counter: object, *labels: object) -> None:
        calls.append((counter, labels))

    # patch the module-level safe_inc used by the view to observe increments
    monkeypatch.setattr(api_views, "safe_inc", fake_inc)

    factory = APIRequestFactory()
    request = factory.post(f"/applications/{application.pk}/accept/")
    request.user = poster

    view = ApplicationViewSet.as_view({"post": "accept"})
    # DRF dispatch returns a Response-like object; call directly in test
    response = view(request, pk=application.pk)

    # DRF should convert Throttled into a 429 response at dispatch time
    assert response.status_code == 429

    # ensure the throttle metric was incremented by the view's except handler
    assert len(calls) >= 1
    _, labels = calls[0]
    assert any("application_accept" in lbl for lbl in labels if isinstance(lbl, str))
