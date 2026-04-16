from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from jobs.models import Job


@pytest.mark.django_db
def test_job_default_status_is_open() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_jobs", password="pass")
    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Test job",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("10.00"),
    )
    assert job.status == Job.JobStatus.OPEN


@pytest.mark.django_db
def test_job_status_can_be_set_to_completed() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_jobs2", password="pass")
    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Completed job",
        description="desc",
        location="loc",
        estimated_hours=2,
        hourly_rate=Decimal("15.00"),
        status=Job.JobStatus.COMPLETED,
    )
    assert job.status == Job.JobStatus.COMPLETED


@pytest.mark.django_db
def test_job_str_returns_title() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_jobs3", password="pass")
    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="My Job Title",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("10.00"),
    )
    assert str(job) == "My Job Title"


@pytest.mark.django_db
def test_job_history_is_tracked() -> None:
    """AuditedModel tracking creates a history record on save."""
    User = get_user_model()
    poster = User.objects.create_user(username="poster_jobs4", password="pass")
    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="History job",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("10.00"),
    )
    assert job.history.count() >= 1  # type: ignore[attr-defined]
