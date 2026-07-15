from django.test import TestCase
from django.urls import reverse

from core.tests.utils import link_coach, make_user


class CoachWorkspaceTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user("athlete")
        link_coach(self.coach, self.athlete)
        self.client.force_login(self.coach)

    def test_coach_home_redirects_to_coaching_workspace(self):
        self.assertRedirects(self.client.get(reverse("core:dashboard")), reverse("coaching:dashboard"))

    def test_workspace_shows_client_and_private_notes_form(self):
        response = self.client.get(reverse("coaching:dashboard"))
        self.assertContains(response, "Coaching workspace")
        self.assertContains(response, self.athlete.display_label)
        self.assertContains(response, "Private coach notes")

    def test_workspace_private_note_saves_to_relationship(self):
        response = self.client.post(
            reverse("coaching:client_notes_save", args=[self.athlete.uuid]),
            {"private_notes": "Watch knee tracking on squat day."},
        )
        self.assertRedirects(response, reverse("coaching:client_detail", args=[self.athlete.uuid]))
        relationship = self.coach.client_relationships.get(client=self.athlete)
        self.assertEqual(relationship.private_notes, "Watch knee tracking on squat day.")
