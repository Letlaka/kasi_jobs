from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_user_display_name_and_phone() -> None:
    user_model = get_user_model()
    pw = "x"
    u: Any = user_model.objects.create_user(
        username="jdoe", first_name="John", last_name="Doe", password=pw
    )
    assert u.display_name == "John Doe"  # noqa: S101 - test assertion
    u.phone = "+27123456789"
    u.save()
    assert u.phone == "+27123456789"  # noqa: S101 - test assertion


# Create your tests here.
