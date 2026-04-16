from decimal import Decimal

import pytest
from applications.models import Application
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from jobs.models import Job
from reviews.models import Review


def _make_job(poster, status=Job.JobStatus.COMPLETED):
    return Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Job",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("10.00"),
        status=status,
    )


@pytest.mark.django_db
def test_review_rejected_for_non_completed_job() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_rv1", password="pass")
    seeker = User.objects.create_user(username="seeker_rv1", password="pass")
    job = _make_job(poster, status=Job.JobStatus.OPEN)
    Application.objects.create(job=job, seeker=seeker, status=Application.ApplicationStatus.ACCEPTED)  # type: ignore[attr-defined]
    review = Review(job=job, reviewer=seeker, rating=4)
    with pytest.raises(ValidationError, match="completed"):
        review.full_clean()


@pytest.mark.django_db
def test_review_rejected_for_poster_self_review() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_rv2", password="pass")
    job = _make_job(poster)
    review = Review(job=job, reviewer=poster, rating=5)
    with pytest.raises(ValidationError, match="poster"):
        review.full_clean()


@pytest.mark.django_db
def test_review_rejected_without_accepted_application() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_rv3", password="pass")
    seeker = User.objects.create_user(username="seeker_rv3", password="pass")
    job = _make_job(poster)
    # No application at all
    review = Review(job=job, reviewer=seeker, rating=3)
    with pytest.raises(ValidationError, match="accepted application"):
        review.full_clean()


@pytest.mark.django_db
def test_review_accepted_for_valid_seeker() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_rv4", password="pass")
    seeker = User.objects.create_user(username="seeker_rv4", password="pass")
    job = _make_job(poster)
    Application.objects.create(job=job, seeker=seeker, status=Application.ApplicationStatus.ACCEPTED)  # type: ignore[attr-defined]
    review = Review(job=job, reviewer=seeker, rating=5, comment="Great!")
    # Should not raise
    review.full_clean()


@pytest.mark.django_db
def test_review_rating_out_of_range() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_rv5", password="pass")
    seeker = User.objects.create_user(username="seeker_rv5", password="pass")
    job = _make_job(poster)
    Application.objects.create(job=job, seeker=seeker, status=Application.ApplicationStatus.ACCEPTED)  # type: ignore[attr-defined]
    review = Review(job=job, reviewer=seeker, rating=10)
    with pytest.raises((ValidationError, ValueError)):
        review.full_clean()
