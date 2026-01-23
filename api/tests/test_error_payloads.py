import pytest


@pytest.mark.django_db
def test_accept_returns_403_payload_for_unauthorized() -> None:
    from api.error_codes import NOT_AUTHORIZED
    from api.views import ApplicationViewSet
    from django.contrib.auth import get_user_model
    from jobs.models import Job
    from rest_framework.test import APIRequestFactory

    User = get_user_model()
    poster = User.objects.create_user(username="poster_err1", password="pw")
    other = User.objects.create_user(username="other_err1", password="pw")
    seeker = User.objects.create_user(username="seeker_err1", password="pw")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Err Job 1",
        description="desc",
        location="here",
        estimated_hours=1,
        hourly_rate="10.00",
    )

    from applications.models import Application

    application = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    factory = APIRequestFactory()
    request = factory.post(f"/applications/{application.pk}/accept/")
    request.user = other
    view = ApplicationViewSet.as_view({"post": "accept"})
    response = view(request, pk=application.pk)

    assert response.status_code == 403
    payload = response.data
    assert isinstance(payload, dict)
    assert payload.get("code") == NOT_AUTHORIZED
    assert "detail" in payload


@pytest.mark.django_db
def test_accept_returns_409_payload_when_not_pending() -> None:
    from api.error_codes import APPLICATION_NOT_PENDING
    from api.views import ApplicationViewSet
    from django.contrib.auth import get_user_model
    from jobs.models import Job
    from rest_framework.test import APIRequestFactory
    from services import applications_service as svc

    User = get_user_model()
    poster = User.objects.create_user(username="poster_err2", password="pw")
    seeker = User.objects.create_user(username="seeker_err2", password="pw")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Err Job 2",
        description="desc",
        location="here",
        estimated_hours=1,
        hourly_rate="12.00",
    )

    from applications.models import Application

    application = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    # accept once
    svc.accept_application(application, poster)

    from django.conf import settings as django_settings

    # Ensure middleware handles exceptions (DRF may re-raise when DEBUG=True)
    django_settings.DEBUG = False

    factory = APIRequestFactory()
    request = factory.post(f"/applications/{application.pk}/accept/")
    request.user = poster
    view = ApplicationViewSet.as_view({"post": "accept"})
    response = view(request, pk=application.pk)

    assert response.status_code == 409
    payload = response.data
    assert isinstance(payload, dict)
    assert payload.get("code") == APPLICATION_NOT_PENDING
    assert "detail" in payload


@pytest.mark.django_db
def test_accept_returns_500_payload_on_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.error_codes import INTERNAL_ERROR
    from api.views import ApplicationViewSet
    from django.contrib.auth import get_user_model
    from jobs.models import Job
    from rest_framework.test import APIRequestFactory

    User = get_user_model()
    poster = User.objects.create_user(username="poster_err3", password="pw")
    seeker = User.objects.create_user(username="seeker_err3", password="pw")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Err Job 3",
        description="desc",
        location="here",
        estimated_hours=1,
        hourly_rate="15.00",
    )

    from applications.models import Application

    application = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    # monkeypatch the view-level accept_application reference to raise
    def boom(app: object, user: object) -> None:
        raise RuntimeError("boom")

    import api.views as api_views

    monkeypatch.setattr(api_views, "accept_application", boom)

    factory = APIRequestFactory()
    request = factory.post(f"/applications/{application.pk}/accept/")
    request.user = poster
    view = ApplicationViewSet.as_view({"post": "accept"})
    response = view(request, pk=application.pk)

    assert response.status_code == 500
    payload = response.data
    assert isinstance(payload, dict)
    assert payload.get("code") == INTERNAL_ERROR
    assert "detail" in payload


def test_service_accept_invalid_application_raises_400() -> None:
    from api.error_codes import APPLICATION_INVALID
    from api.errors import ApiError

    # unsaved Application instance (no pk) should trigger APPLICATION_INVALID
    from applications.models import Application as AppModel
    from services import applications_service as svc

    app = AppModel(job=None, seeker=None)
    with pytest.raises(ApiError) as exc:
        svc.accept_application(app, object())
    assert exc.value.code == APPLICATION_INVALID
