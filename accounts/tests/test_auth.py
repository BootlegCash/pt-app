from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from accounts.models import User
from accounts.services import create_user_account
from core.tests.utils import make_admin, make_user


class RegistrationDisabledTests(TestCase):
    def test_no_public_registration_url(self):
        for name in ("register", "signup", "accounts:register", "accounts:signup"):
            with self.assertRaises(NoReverseMatch):
                reverse(name)
        self.assertEqual(self.client.get("/accounts/register/").status_code, 404)
        self.assertEqual(self.client.get("/accounts/signup/").status_code, 404)

    def test_login_page_public(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "contact your administrator", status_code=200)


class AccountCreationTests(TestCase):
    def test_service_creates_user_profile_and_relationship(self):
        admin = make_admin()
        coach = make_user(is_coach=True)
        user, password = create_user_account(
            username="newathlete", email="newathlete@example.com",
            coach=coach, created_by=admin,
        )
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.check_password(password))
        self.assertTrue(hasattr(user, "athlete_profile"))
        self.assertTrue(
            user.coach_relationships.filter(coach=coach, status="active").exists()
        )

    def test_admin_create_user_view_requires_admin(self):
        athlete = make_user()
        self.client.force_login(athlete)
        self.assertEqual(self.client.get(reverse("coaching:create_user")).status_code, 403)
        admin = make_admin()
        self.client.force_login(admin)
        response = self.client.post(reverse("coaching:create_user"), {
            "username": "fresh", "email": "fresh@example.com",
            "is_athlete": "on", "active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="fresh").exists())


class LoginTests(TestCase):
    def test_login_with_username_and_email(self):
        make_user("logan", password="secret-pass-999")
        for identifier in ("logan", "logan@example.com"):
            self.client.logout()
            ok = self.client.login(username=identifier, password="secret-pass-999")
            self.assertTrue(ok, f"login failed for {identifier}")

    def test_logout(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 302)  # redirected to login

    def test_inactive_user_cannot_login(self):
        user = make_user(password="secret-pass-999")
        user.is_active = False
        user.save()
        self.assertFalse(self.client.login(username=user.username, password="secret-pass-999"))

    @override_settings(LOGIN_RATE_LIMIT_ATTEMPTS=3)
    def test_login_rate_limited_after_failures(self):
        make_user("target", password="secret-pass-999")
        url = reverse("accounts:login")
        for _ in range(3):
            self.client.post(url, {"username": "target", "password": "wrong"})
        response = self.client.post(url, {"username": "target", "password": "secret-pass-999"})
        self.assertContains(response, "Too many failed attempts", status_code=200)


class ForcedPasswordChangeTests(TestCase):
    def test_redirects_until_password_changed(self):
        user = make_user(must_change_password=True)
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertRedirects(response, reverse("accounts:force_password_change"))
        response = self.client.post(reverse("accounts:force_password_change"), {
            "new_password1": "brand-new-pass-42", "new_password2": "brand-new-pass-42",
        })
        self.assertRedirects(response, reverse("core:dashboard"))
        user.refresh_from_db()
        self.assertFalse(user.must_change_password)
        self.assertEqual(self.client.get("/").status_code, 200)


class DataExportDeactivationTests(TestCase):
    def test_export_returns_own_data(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:export_data"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["account"]["username"], user.username)

    def test_deactivate_requires_correct_password(self):
        user = make_user(password="secret-pass-999")
        self.client.force_login(user)
        self.client.post(reverse("accounts:deactivate"), {"password": "wrong"})
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.client.post(reverse("accounts:deactivate"), {"password": "secret-pass-999"})
        user.refresh_from_db()
        self.assertFalse(user.is_active)
