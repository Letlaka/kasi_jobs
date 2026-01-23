from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from accounts.security.mfa_middleware import RequireMFAForAdminMiddleware

User = get_user_model()


class RequireMFAMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = lambda req: HttpResponse("ok")

    def _create_staff(self):
        return User.objects.create_user(username="staff", password="x", is_staff=True)

    @override_settings(DEBUG=True)
    def test_bypass_in_debug(self):
        req = self.factory.get("/admin/")
        req.user = self._create_staff()
        mw = RequireMFAForAdminMiddleware(self.get_response)
        resp = mw(req)
        self.assertEqual(resp.status_code, 200)

    @override_settings(DEBUG=False)
    def test_redirects_when_mfa_not_enabled(self):
        req = self.factory.get("/admin/some")
        req.user = self._create_staff()

        # Patch allauth.app_settings to report MFA enabled in config, and
        # patch the MFA adapter to report the user has no MFA configured.
        with patch("accounts.security.mfa_middleware.reverse", return_value="/accounts/2fa/"):
            with patch("allauth.app_settings") as allauth_app_settings:
                allauth_app_settings.MFA_ENABLED = True
                with patch("allauth.mfa.adapter.get_adapter") as get_adapter:
                    adapter = MagicMock()
                    adapter.is_mfa_enabled.return_value = False
                    get_adapter.return_value = adapter

                    mw = RequireMFAForAdminMiddleware(self.get_response)
                    resp = mw(req)

        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/2fa/", resp["Location"])

    @override_settings(DEBUG=False)
    def test_allows_when_mfa_enabled_for_user(self):
        req = self.factory.get("/admin/other")
        req.user = self._create_staff()

        with patch("allauth.app_settings") as allauth_app_settings:
            allauth_app_settings.MFA_ENABLED = True
            with patch("allauth.mfa.adapter.get_adapter") as get_adapter:
                adapter = MagicMock()
                adapter.is_mfa_enabled.return_value = True
                get_adapter.return_value = adapter

                mw = RequireMFAForAdminMiddleware(self.get_response)
                resp = mw(req)

        self.assertEqual(resp.status_code, 200)
