import pytest
from django.contrib.auth import get_user_model
from profiles.models.poster import PosterProfile
from profiles.models.seeker import SeekerProfile


@pytest.mark.django_db
def test_seeker_profile_str_includes_username() -> None:
    User = get_user_model()
    user = User.objects.create_user(username="seeker_prof1", password="pass")
    profile = SeekerProfile.objects.create(user=user)  # type: ignore[attr-defined]
    assert "seeker_prof1" in str(profile)


@pytest.mark.django_db
def test_poster_profile_str_falls_back_to_username() -> None:
    User = get_user_model()
    user = User.objects.create_user(username="poster_prof1", password="pass")
    profile = PosterProfile.objects.create(user=user)  # type: ignore[attr-defined]
    assert "poster_prof1" in str(profile)


@pytest.mark.django_db
def test_seeker_profile_history_tracked() -> None:
    User = get_user_model()
    user = User.objects.create_user(username="seeker_prof2", password="pass")
    profile = SeekerProfile.objects.create(user=user)  # type: ignore[attr-defined]
    profile.bio = "Updated bio"
    profile.save()
    assert profile.history.count() >= 2  # type: ignore[attr-defined]


@pytest.mark.django_db
def test_signed_url_round_trip() -> None:
    """Signed URL generation and verification use the same salt."""
    import tempfile

    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.test import override_settings
    from django.urls import reverse

    User = get_user_model()
    user = User.objects.create_user(username="seeker_url1", password="pass")

    with override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="kasi_tests_url_")):
        profile = SeekerProfile.objects.create(user=user)  # type: ignore[attr-defined]
        f = SimpleUploadedFile("id.pdf", b"PDFDATA", content_type="application/pdf")
        profile.id_document.save("id_verification/test_url.pdf", f)
        profile.save()

        info = profile.get_signed_document_url()
        assert info is not None
        assert "token" in info
        assert "url" in info
