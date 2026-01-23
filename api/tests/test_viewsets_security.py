from decimal import Decimal

import pytest
from applications.models import Application
from django.contrib.auth import get_user_model
from jobs.models import Job
from profiles.models.seeker import SeekerProfile
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_job_applications_list_forbidden_to_non_poster() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster", password="pass")
    seeker = User.objects.create_user(username="seeker", password="pass")
    other = User.objects.create_user(username="other", password="pass")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Test Job",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("10.00"),
    )
    Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    client = APIClient()
    client.force_authenticate(user=other)
    url = f"/api/v1/jobs/{job.pk}/applications/"
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_job_application_create_conflict_on_closed_job() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster2", password="pass")
    seeker = User.objects.create_user(username="seeker2", password="pass")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Closed Job",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("12.00"),
        status=Job.JobStatus.CLOSED,
    )

    client = APIClient()
    client.force_authenticate(user=seeker)
    url = f"/api/v1/jobs/{job.pk}/applications/"
    response = client.post(url, data={"cover_note": "I'd like this"})
    assert response.status_code == 409
    assert response.json().get("code") == "job_not_open"


@pytest.mark.django_db
def test_top_level_applications_create_not_allowed() -> None:
    User = get_user_model()
    seeker = User.objects.create_user(username="seeker3", password="pass")
    client = APIClient()
    client.force_authenticate(user=seeker)
    url = "/api/v1/applications/"
    response = client.post(url, data={})
    assert response.status_code == 405


@pytest.mark.django_db
def test_accept_forbidden_for_non_poster() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster3", password="pass")
    seeker = User.objects.create_user(username="seeker4", password="pass")
    other = User.objects.create_user(username="other2", password="pass")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Another Job",
        description="desc",
        location="loc",
        estimated_hours=2,
        hourly_rate=Decimal("20.00"),
    )
    app = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    client = APIClient()
    client.force_authenticate(user=other)
    url = f"/api/v1/applications/{app.pk}/accept/"
    response = client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_seeker_profile_detail_not_accessible_by_other_user() -> None:
    User = get_user_model()
    user_a = User.objects.create_user(username="user_a", password="pass")
    user_b = User.objects.create_user(username="user_b", password="pass")

    profile_a = SeekerProfile.objects.create(user=user_a)  # type: ignore[attr-defined]
    profile_b = SeekerProfile.objects.create(user=user_b)  # type: ignore[attr-defined]

    client = APIClient()
    client.force_authenticate(user=user_a)
    url = f"/api/v1/profiles/{profile_b.pk}/"
    response = client.get(url)
    # The view scopes queryset to the requesting user, so other profiles are not found
    assert response.status_code == 404


@pytest.mark.django_db
def test_application_detail_not_found_for_unrelated_user() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_x", password="pass")
    seeker = User.objects.create_user(username="seeker_x", password="pass")
    other = User.objects.create_user(username="other_x", password="pass")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Job X",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("15.00"),
    )
    app = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    client = APIClient()
    client.force_authenticate(user=other)
    url = f"/api/v1/applications/{app.pk}/"
    response = client.get(url)
    # The view scopes the queryset so unrelated authenticated users get 404
    assert response.status_code == 404


@pytest.mark.django_db
def test_reject_forbidden_for_non_poster() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_reject", password="pass")
    seeker = User.objects.create_user(username="seeker_reject", password="pass")
    other = User.objects.create_user(username="other_reject", password="pass")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Job Reject",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("18.00"),
    )
    app = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    client = APIClient()
    client.force_authenticate(user=other)
    url = f"/api/v1/applications/{app.pk}/reject/"
    response = client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_job_applications_list_allowed_for_poster() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_allowed", password="pass")
    seeker = User.objects.create_user(username="seeker_allowed", password="pass")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Job Allowed",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("20.00"),
    )
    Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    client = APIClient()
    client.force_authenticate(user=poster)
    url = f"/api/v1/jobs/{job.pk}/applications/"
    response = client.get(url)
    assert response.status_code == 200
