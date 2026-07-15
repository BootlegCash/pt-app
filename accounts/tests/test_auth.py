from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from accounts.models import LoginAttempt, User
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

    def test_admin_cannot_create_user_with_weak_temporary_password(self):
        admin = make_admin()
        self.client.force_login(admin)

        response = self.client.post(reverse("coaching:create_user"), {
            "username": "weakuser", "email": "weak@example.com",
            "is_athlete": "on", "active": "on", "temporary_password": "duck",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "too short")
        self.assertFalse(User.objects.filter(username="weakuser").exists())


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

    @override_settings(LOGIN_RATE_LIMIT_ATTEMPTS=3)
    def test_failed_attempts_do_not_lock_user_out_from_another_ip(self):
        make_user("target", password="secret-pass-999")
        url = reverse("accounts:login")
        for _ in range(3):
            self.client.post(
                url, {"username": "target", "password": "wrong"},
                REMOTE_ADDR="203.0.113.10",
            )
        response = self.client.post(
            url, {"username": "target", "password": "secret-pass-999"},
            REMOTE_ADDR="203.0.113.20",
        )
        self.assertEqual(response.status_code, 302)

    @override_settings(LOGIN_RATE_LIMIT_ATTEMPTS=3, TRUST_X_FORWARDED_FOR=False)
    def test_spoofed_forwarded_addresses_do_not_bypass_ip_limit(self):
        make_user("target", password="secret-pass-999")
        url = reverse("accounts:login")
        for index in range(3):
            self.client.post(
                url, {"username": "target", "password": "wrong"},
                REMOTE_ADDR="203.0.113.10",
                HTTP_X_FORWARDED_FOR=f"198.51.100.{index}",
            )

        response = self.client.post(
            url, {"username": "target", "password": "secret-pass-999"},
            REMOTE_ADDR="203.0.113.10",
            HTTP_X_FORWARDED_FOR="198.51.100.99",
        )

        self.assertContains(response, "Too many failed attempts", status_code=200)

    @override_settings(LOGIN_RATE_LIMIT_ATTEMPTS=3)
    def test_successful_login_does_not_clear_failures_for_another_account(self):
        make_user("victim", password="victim-pass-999")
        make_user("attacker", password="attacker-pass-999")
        url = reverse("accounts:login")
        for _ in range(2):
            self.client.post(url, {"username": "victim", "password": "wrong"})
        self.client.post(
            url, {"username": "attacker", "password": "attacker-pass-999"}
        )
        self.client.logout()
        self.client.post(url, {"username": "victim", "password": "wrong"})

        response = self.client.post(
            url, {"username": "victim", "password": "victim-pass-999"}
        )

        self.assertContains(response, "Too many failed attempts", status_code=200)

    def test_expired_login_attempts_are_pruned(self):
        attempt = LoginAttempt.objects.create(
            username="old", ip_address="203.0.113.10"
        )
        LoginAttempt.objects.filter(pk=attempt.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=1)
        )

        self.client.post(
            reverse("accounts:login"),
            {"username": "current", "password": "wrong"},
            REMOTE_ADDR="203.0.113.10",
        )

        self.assertFalse(LoginAttempt.objects.filter(pk=attempt.pk).exists())

    @override_settings(LOGIN_RATE_LIMIT_ATTEMPTS=2)
    def test_admin_login_uses_same_throttle(self):
        admin = make_admin()
        for _ in range(2):
            self.client.post(
                "/admin/login/", {"username": admin.username, "password": "wrong"}
            )
        response = self.client.post(
            "/admin/login/",
            {"username": admin.username, "password": "adminpass-12345"},
        )
        self.assertContains(response, "Too many failed attempts", status_code=200)

    def test_authenticated_nonstaff_admin_visit_does_not_redirect_loop(self):
        athlete = make_user()
        self.client.force_login(athlete)

        response = self.client.get("/admin/", follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.redirect_chain), 2)

    def test_staff_admin_login_returns_to_admin(self):
        admin_user = make_admin()

        response = self.client.post(
            "/admin/login/?next=/admin/",
            {"username": admin_user.username, "password": "adminpass-12345"},
        )

        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)


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
        self.assertEqual(response["Cache-Control"], "private, no-store")
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
