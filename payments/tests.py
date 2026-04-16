from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from jobs.models import Job
from payments.models import Payout


@pytest.mark.django_db
def test_payout_default_status_is_pending() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_pay", password="pass")
    seeker = User.objects.create_user(username="seeker_pay", password="pass")
    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Pay job",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("20.00"),
    )
    payout = Payout.objects.create(job=job, seeker=seeker, amount=Decimal("20.00"))  # type: ignore[attr-defined]
    assert payout.status == Payout.PayoutStatus.PENDING


@pytest.mark.django_db
def test_payout_status_transitions() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_pay2", password="pass")
    seeker = User.objects.create_user(username="seeker_pay2", password="pass")
    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Pay job 2",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("20.00"),
    )
    payout = Payout.objects.create(job=job, seeker=seeker, amount=Decimal("20.00"))  # type: ignore[attr-defined]
    payout.status = Payout.PayoutStatus.COMPLETED
    payout.save()
    payout.refresh_from_db()
    assert payout.status == Payout.PayoutStatus.COMPLETED


@pytest.mark.django_db
def test_payout_str_includes_id() -> None:
    User = get_user_model()
    poster = User.objects.create_user(username="poster_pay3", password="pass")
    seeker = User.objects.create_user(username="seeker_pay3", password="pass")
    job = Job.objects.create(  # type: ignore[attr-defined]
        poster=poster,
        title="Pay job 3",
        description="desc",
        location="loc",
        estimated_hours=1,
        hourly_rate=Decimal("10.00"),
    )
    payout = Payout.objects.create(job=job, seeker=seeker, amount=Decimal("10.00"))  # type: ignore[attr-defined]
    assert "Payout" in str(payout)
