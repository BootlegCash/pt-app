from django.test import TestCase
from django.urls import reverse

from coaching.models import CoachClientRelationship
from core.services.access import can_manage_client, can_view_client
from core.tests.utils import (
    assign_program,
    link_coach,
    make_admin,
    make_program,
    make_user,
)


class AccessRuleTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.client_user = make_user()
        self.stranger = make_user()

    def test_owner_can_view_self_but_not_manage(self):
        self.assertTrue(can_view_client(self.client_user, self.client_user))
        self.assertFalse(can_manage_client(self.client_user, self.client_user))

    def test_admin_can_view_and_manage(self):
        admin = make_admin()
        self.assertTrue(can_view_client(admin, self.client_user))
        self.assertTrue(can_manage_client(admin, self.client_user))

    def test_coach_requires_active_relationship(self):
        self.assertFalse(can_view_client(self.coach, self.client_user))
        relationship = link_coach(self.coach, self.client_user)
        self.assertTrue(can_view_client(self.coach, self.client_user))
        self.assertTrue(can_manage_client(self.coach, self.client_user))
        for status in ("pending", "paused", "ended"):
            relationship.status = status
            relationship.save()
            self.assertFalse(can_view_client(self.coach, self.client_user), status)

    def test_stranger_cannot_view(self):
        self.assertFalse(can_view_client(self.stranger, self.client_user))


class UserIsolationTests(TestCase):
    """Users only ever see their own rows; other users' pages 403/404."""

    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        link_coach(self.coach, self.alice)
        program = make_program(self.coach)
        assign_program(program, self.alice)
        self.alice_session = self.alice.scheduled_sessions.first()

    def test_client_pages_show_own_data_only(self):
        self.client.force_login(self.bob)
        response = self.client.get(reverse("programs:my_program"))
        self.assertContains(response, "No active program")

    def test_other_users_scheduled_session_is_404(self):
        self.client.force_login(self.bob)
        response = self.client.get(
            reverse("calendar_app:day_detail", args=[self.alice_session.uuid])
        )
        self.assertEqual(response.status_code, 404)

    def test_other_users_workout_start_is_404(self):
        self.client.force_login(self.bob)
        response = self.client.get(
            reverse("workouts:start", args=[self.alice_session.uuid])
        )
        self.assertEqual(response.status_code, 404)

    def test_coach_pages_forbidden_for_athletes(self):
        self.client.force_login(self.bob)
        for name in ("coaching:dashboard", "coaching:client_list",
                     "coaching:progression_approvals", "coaching:pain_flags",
                     "programs:builder_list", "imports:approvals"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_unassigned_coach_cannot_open_client(self):
        other_coach = make_user(is_coach=True)
        self.client.force_login(other_coach)
        response = self.client.get(
            reverse("coaching:client_detail", args=[self.alice.uuid])
        )
        self.assertEqual(response.status_code, 403)

    def test_assigned_coach_can_open_client(self):
        self.client.force_login(self.coach)
        response = self.client.get(
            reverse("coaching:client_detail", args=[self.alice.uuid])
        )
        self.assertEqual(response.status_code, 200)

    def test_client_cannot_edit_own_profile_via_coach_url(self):
        self.client.force_login(self.alice)
        response = self.client.get(
            reverse("coaching:client_profile_edit", args=[self.alice.uuid])
        )
        self.assertEqual(response.status_code, 403)

    def test_chart_api_scoped_to_owner(self):
        self.client.force_login(self.bob)
        response = self.client.get(
            reverse("progress:chart_data", args=["bodyweight"]) + f"?client={self.alice.uuid}"
        )
        self.assertEqual(response.status_code, 404)
        self.client.force_login(self.coach)
        response = self.client.get(
            reverse("progress:chart_data", args=["bodyweight"]) + f"?client={self.alice.uuid}"
        )
        self.assertEqual(response.status_code, 200)


class RelationshipModelTests(TestCase):
    def test_timestamps_set_on_status_change(self):
        coach, client = make_user(is_coach=True), make_user()
        relationship = link_coach(coach, client, status=CoachClientRelationship.Status.PENDING)
        self.assertIsNone(relationship.activated_at)
        relationship.status = CoachClientRelationship.Status.ACTIVE
        relationship.save()
        self.assertIsNotNone(relationship.activated_at)
        relationship.status = CoachClientRelationship.Status.ENDED
        relationship.save()
        self.assertIsNotNone(relationship.ended_at)
