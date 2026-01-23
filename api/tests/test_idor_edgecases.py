from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from jobs.models import Job
from profiles.models.seeker import SeekerProfile
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_cannot_patch_other_users_profile() -> None:
    User = get_user_model()
    user_a = User.objects.create_user(username="a", password="pass")
    user_b = User.objects.create_user(username="b", password="pass")

    profile_b = SeekerProfile.objects.create(user=user_b)  # type: ignore[attr-defined]

    client = APIClient()
    client.force_authenticate(user=user_a)
    url = f"/api/v1/profiles/{profile_b.pk}/"
    response = client.patch(url, data={"bio": "hacked"})

    # The API scopes profiles to the requesting user; other profiles should not be reachable
    # The viewset may be read-only (405) or return 404/403 — accept any of these.
    assert response.status_code in (404, 403, 405)


@pytest.mark.django_db
def test_non_poster_cannot_modify_job() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_mod", password="pass")
    other = User.objects.create_user(username="other_mod", password="pass")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Immutable Job",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("30.00"),
    )

    client = APIClient()
    client.force_authenticate(user=other)
    url = f"/api/v1/jobs/{job.pk}/"
    response = client.patch(url, data={"title": "I changed it"})

    # Non-poster should not be allowed to modify the job
    assert response.status_code in (403, 404)


@pytest.mark.django_db
def test_cannot_view_other_users_applications_via_idor() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_view", password="pass")
    seeker = User.objects.create_user(username="seeker_view", password="pass")
    other = User.objects.create_user(username="other_view", password="pass")

    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Visible Job",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("25.00"),
    )

    # seeker applies
    from applications.models import Application

    app = Application.objects.create(job=job, seeker=seeker)  # type: ignore[attr-defined]

    client = APIClient()
    client.force_authenticate(user=other)
    url = f"/api/v1/applications/{app.pk}/"
    response = client.get(url)

    # The view should not leak application details to unrelated users
    assert response.status_code == 404
