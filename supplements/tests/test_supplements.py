from django.test import TestCase
from django.urls import reverse

from core.tests.utils import link_coach, make_user
from supplements.models import Supplement, UserSupplementRecommendation


class SupplementAssignmentTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user()
        link_coach(self.coach, self.athlete)
        self.supplement = Supplement.objects.create(
            name="Creatine monohydrate", category="performance",
            purpose="Supports strength output.", default_dose="3-5", dose_unit="g/day",
        )
        self.url = reverse("supplements:coach_assign", args=[self.athlete.uuid])

    def test_client_cannot_assign_supplements(self):
        self.client.force_login(self.athlete)
        response = self.client.post(self.url, {
            "supplement": self.supplement.pk, "assigned_dose": "5",
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(UserSupplementRecommendation.objects.count(), 0)

    def test_coach_assigns_and_client_views(self):
        self.client.force_login(self.coach)
        response = self.client.post(self.url, {
            "supplement": self.supplement.pk, "assigned_dose": "5",
            "dose_unit": "g/day", "timing": "any time", "frequency": "daily",
            "reason": "strength support", "coach_notes": "", "active": "on",
        })
        self.assertEqual(response.status_code, 302)
        recommendation = UserSupplementRecommendation.objects.get(user=self.athlete)
        self.assertEqual(recommendation.entered_by, self.coach)

        self.client.force_login(self.athlete)
        response = self.client.get(reverse("supplements:me"))
        self.assertContains(response, "Creatine monohydrate")
        self.assertContains(response, "not medical advice")

    def test_unrelated_coach_cannot_assign(self):
        other_coach = make_user(is_coach=True)
        self.client.force_login(other_coach)
        response = self.client.post(self.url, {
            "supplement": self.supplement.pk, "assigned_dose": "5",
        })
        self.assertEqual(response.status_code, 403)

    def test_default_entries_are_conservative(self):
        from supplements.defaults import DEFAULT_SUPPLEMENTS

        by_name = {spec["name"]: spec for spec in DEFAULT_SUPPLEMENTS}
        self.assertIn("3–5", by_name["Creatine monohydrate"]["default_dose"])
        self.assertIn("350 mg", by_name["Magnesium"]["maximum_recommended_amount"])
        self.assertIn("400 mg", by_name["Caffeine"]["maximum_recommended_amount"])
        self.assertTrue(by_name["Caffeine"]["bodyweight_based"])
        self.assertIn("4000 IU", by_name["Vitamin D3"]["maximum_recommended_amount"])
