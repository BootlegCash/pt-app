from django.test import TestCase
from django.urls import reverse

from core.models import AuditRecord
from core.tests.utils import link_coach, make_user


class AuditTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user()
        link_coach(self.coach, self.athlete)

    def test_profile_edit_audited(self):
        self.client.force_login(self.coach)
        profile = self.athlete.athlete_profile
        response = self.client.post(
            reverse("coaching:client_profile_edit", args=[self.athlete.uuid]),
            {
                "display_name": "New Name", "training_goal": "cut",
                "training_experience": "beginner", "activity_level": "light",
                "occupation_activity": "seated", "weekly_lifting_days": 3,
                "weekly_running_days": 0, "account_status": "active",
                "general_notes": "", "movement_limitations": "", "injury_cautions": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.display_name, "New Name")
        self.assertTrue(AuditRecord.objects.filter(
            changed_by=self.coach, affected_user=self.athlete,
            object_type="AthleteProfile", field_changed="display_name",
            new_value="New Name",
        ).exists())

    def test_measurement_entry_audited(self):
        self.client.force_login(self.coach)
        self.client.post(
            reverse("coaching:client_measurements", args=[self.athlete.uuid]),
            {"date": "2026-07-01", "bodyweight_lb": "185.0",
             "measurement_method": "tape", "notes": ""},
        )
        self.assertTrue(AuditRecord.objects.filter(
            affected_user=self.athlete, object_type="Measurement",
        ).exists())

    def test_clients_cannot_see_audit_admin(self):
        self.client.force_login(self.athlete)
        response = self.client.get("/admin/core/auditrecord/")
        self.assertEqual(response.status_code, 302)  # redirected to admin login
