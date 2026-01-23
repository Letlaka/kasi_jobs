import pytest
from rest_framework.test import APIRequestFactory


@pytest.mark.django_db
def test_accept_view_sets_throttle_and_records_audit_and_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Behavioral test: exercise the accept action and assert runtime
    throttle scope, audit record, and metric helper invocation.
    """
    from api.throttle_scopes import THROTTLE_APPLICATION_ACCEPT
    from api.views import ApplicationViewSet
    from applications.models import ACTION_ACCEPT, Application, ApplicationAction
    from django.contrib.auth import get_user_model
    from jobs.models import Job
    from services import applications_service as svc

    User = get_user_model()
    poster = User.objects.create_user(username="poster_view", password="pw")
    seeker = User.objects.create_user(username="seeker_view", password="pw")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="View Job",
        description="desc",
        location="here",
        estimated_hours=1,
        hourly_rate="20.00",
    )

    application = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    recorded = {"throttle_scope": None}

    def fake_check_throttles(self: object, request: object) -> None:
        # capture the throttle_scope at the time throttles are checked
        recorded["throttle_scope"] = getattr(self, "throttle_scope", None)

    monkeypatch.setattr(ApplicationViewSet, "check_throttles", fake_check_throttles)

    metric_calls = {"inc": 0, "obs": 0}

    def fake_inc(counter: object, *labels: object) -> None:
        metric_calls["inc"] += 1

    def fake_obs(hist: object, value: object) -> None:
        metric_calls["obs"] += 1

    monkeypatch.setattr(svc, "safe_inc", fake_inc)
    monkeypatch.setattr(svc, "safe_observe", fake_obs)

    factory = APIRequestFactory()
    request = factory.post(f"/applications/{application.pk}/accept/")
    request.user = poster

    view = ApplicationViewSet.as_view({"post": "accept"})
    response = view(request, pk=application.pk)

    assert response.status_code == 200
    assert recorded["throttle_scope"] == THROTTLE_APPLICATION_ACCEPT

    # single audit record created and metrics invoked
    assert ApplicationAction.objects.filter(application=application, action=ACTION_ACCEPT).exists()  # type: ignore[attr-defined]
    assert metric_calls["inc"] >= 1
    assert metric_calls["obs"] >= 1
