import tempfile
import time
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from profiles.models.seeker import SeekerProfile


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="kasi_tests_"))
class SignedURLTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u1", password="pass")
        self.other = User.objects.create_user(username="u2", password="pass")

    def _create_profile_with_file(self):
        profile = SeekerProfile.objects.create(user=self.user)
        content = b"PDFDATA"
        f = SimpleUploadedFile("id.pdf", content, content_type="application/pdf")
        profile.id_document.save("id_verification/test.pdf", f)
        profile.save()
        return profile, content

    def test_owner_can_download_signed_url(self):
        profile, content = self._create_profile_with_file()
        info = profile.get_signed_document_url()
        assert info and "url" in info
        parsed = urlparse(info["url"])
        resp = self.client.get(parsed.path)
        # unauthenticated should be forbidden
        self.assertEqual(resp.status_code, 403)

        # authenticated owner
        self.client.force_login(self.user)
        resp = self.client.get(parsed.path)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, content)

    @override_settings(SIGNED_URL_MAX_AGE=1)
    def test_token_expires(self):
        profile, content = self._create_profile_with_file()
        info = profile.get_signed_document_url()
        parsed = urlparse(info["url"])

        self.client.force_login(self.user)
        resp = self.client.get(parsed.path)
        self.assertEqual(resp.status_code, 200)

        # wait for expiry
        time.sleep(1.5)
        resp = self.client.get(parsed.path)
        self.assertEqual(resp.status_code, 404)

    def test_forbidden_for_other_user(self):
        profile, _ = self._create_profile_with_file()
        info = profile.get_signed_document_url()
        parsed = urlparse(info["url"])

        self.client.force_login(self.other)
        resp = self.client.get(parsed.path)
        self.assertEqual(resp.status_code, 403)

    def test_missing_file_returns_404(self):
        profile, _ = self._create_profile_with_file()
        info = profile.get_signed_document_url()
        parsed = urlparse(info["url"])

        # Remove the stored file
        try:
            profile.id_document.delete(save=False)
        except Exception:
            pass

        self.client.force_login(self.user)
        resp = self.client.get(parsed.path)
        self.assertEqual(resp.status_code, 404)
