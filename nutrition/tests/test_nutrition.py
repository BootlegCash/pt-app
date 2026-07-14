from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.models import AuditRecord
from core.tests.utils import link_coach, make_user
from nutrition.models import MacroRuleSet, NutritionTarget
from nutrition.services.calculator import (
    calculate_targets,
    katch_mcardle_bmr,
    mifflin_st_jeor_bmr,
)
from nutrition.services.weight_trend import trend_recommendation, weekly_averages
from profiles.models import Measurement


class CalculatorTests(TestCase):
    def setUp(self):
        self.ruleset = MacroRuleSet.get_active()

    def test_mifflin_reference_value(self):
        # 80 kg (176.4 lb), 180 cm (70.87 in), 30 y male: 10*80+6.25*180-5*30+5 = 1780
        bmr = mifflin_st_jeor_bmr(sex="male", weight_lb=176.37, height_inches=70.866, age=30)
        self.assertAlmostEqual(bmr, 1780, delta=2)

    def test_mifflin_female_offset(self):
        male = mifflin_st_jeor_bmr(sex="male", weight_lb=150, height_inches=65, age=30)
        female = mifflin_st_jeor_bmr(sex="female", weight_lb=150, height_inches=65, age=30)
        self.assertAlmostEqual(male - female, 166, delta=0.01)

    def test_katch_reference_value(self):
        # 80 kg at 20% BF => 64 kg lean => 370 + 21.6*64 = 1752.4
        bmr = katch_mcardle_bmr(weight_lb=176.37, body_fat_percent=20)
        self.assertAlmostEqual(bmr, 1752.4, delta=2)

    def _calculate(self, goal, **kwargs):
        defaults = dict(
            sex="male", age=30, height_inches=70, weight_lb=185,
            activity_level="moderate", occupation_activity="seated",
            weekly_lifting_days=4, weekly_cardio_days=1,
            goal=goal, ruleset=self.ruleset,
        )
        defaults.update(kwargs)
        return calculate_targets(**defaults)

    def test_cut_creates_deficit(self):
        result = self._calculate("cut", rate_lb_per_week=1)
        self.assertEqual(
            result["calories"], result["maintenance_calories"] - 500
        )
        self.assertEqual(float(result["expected_weekly_change_lb"]), -1.0)

    def test_lean_bulk_creates_surplus(self):
        result = self._calculate("lean_bulk", rate_lb_per_week=0.5)
        self.assertEqual(result["calories"], result["maintenance_calories"] + 250)

    def test_maintain_matches_tdee(self):
        result = self._calculate("maintain")
        self.assertEqual(result["calories"], result["maintenance_calories"])

    def test_cut_uses_higher_protein(self):
        cut = self._calculate("cut", rate_lb_per_week=1)
        maintain = self._calculate("maintain")
        self.assertGreater(cut["protein_g"], maintain["protein_g"])

    def test_macros_roughly_sum_to_calories(self):
        result = self._calculate("maintain")
        macro_calories = (
            result["protein_g"] * 4 + result["carbs_g"] * 4 + result["fat_g"] * 9
        )
        self.assertAlmostEqual(macro_calories, result["calories"], delta=25)

    def test_katch_used_when_requested(self):
        result = self._calculate("maintain", body_fat_percent=18, use_katch=True)
        self.assertEqual(result["method"], "katch")

    def test_aggressive_cut_warned(self):
        result = self._calculate("cut", rate_lb_per_week=2.5)
        self.assertTrue(any("guideline" in w for w in result["warnings"]))

    def test_calorie_floor(self):
        result = self._calculate(
            "cut", rate_lb_per_week=3, weight_lb=95, height_inches=58, age=60,
            sex="female", activity_level="sedentary",
        )
        self.assertGreaterEqual(result["calories"], 1200)


class OverrideAndPermissionTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user()
        link_coach(self.coach, self.athlete)
        self.url = reverse("nutrition:coach_calculator", args=[self.athlete.uuid])

    def test_client_cannot_open_calculator(self):
        self.client.force_login(self.athlete)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_override_saved_and_audited_and_displayed(self):
        self.client.force_login(self.coach)
        response = self.client.post(self.url, {
            "save_overrides": "1", "final_calories": 2400, "final_protein_g": 200,
            "sodium_guidance": "", "pre_workout_suggestion": "",
            "post_workout_suggestion": "", "example_meals": "", "coach_notes": "hi",
        })
        self.assertEqual(response.status_code, 302)
        target = NutritionTarget.objects.get(user=self.athlete)
        self.assertEqual(target.final_calories, 2400)
        self.assertTrue(AuditRecord.objects.filter(
            affected_user=self.athlete, field_changed="final_calories",
        ).exists())
        # final value wins over calculated on the client page
        target.calculated_calories = 2600
        target.save()
        self.assertEqual(target.macro_calories, 2400)
        self.client.force_login(self.athlete)
        response = self.client.get(reverse("nutrition:me"))
        self.assertContains(response, "2400")


class WeightTrendTests(TestCase):
    def setUp(self):
        self.athlete = make_user()
        self.target = NutritionTarget.objects.create(
            user=self.athlete, expected_weekly_change_lb=Decimal("-0.5"),
        )

    def _add_weights(self, weekly_weights, readings_per_week=3):
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        for weeks_ago, weight in enumerate(reversed(weekly_weights)):
            week_start = monday - timedelta(weeks=weeks_ago)
            for reading in range(readings_per_week):
                Measurement.objects.create(
                    user=self.athlete, date=week_start + timedelta(days=reading * 2),
                    bodyweight_lb=Decimal(str(weight + reading * 0.1)),
                )

    def test_insufficient_data(self):
        result = trend_recommendation(self.athlete, self.target)
        self.assertEqual(result["action"], "collect_data")

    def test_on_track_maintains(self):
        self._add_weights([186.0, 185.5, 185.0])  # ~-0.5/wk vs target -0.5
        result = trend_recommendation(self.athlete, self.target)
        self.assertEqual(result["action"], "maintain")

    def test_losing_too_fast_increases(self):
        self._add_weights([188.0, 186.5, 185.0])  # -1.5/wk vs target -0.5
        result = trend_recommendation(self.athlete, self.target)
        self.assertEqual(result["action"], "increase")

    def test_not_losing_decreases(self):
        self._add_weights([185.0, 185.2, 185.4])  # gaining vs target loss
        result = trend_recommendation(self.athlete, self.target)
        self.assertEqual(result["action"], "decrease")

    def test_sparse_data_checks_adherence(self):
        self._add_weights([186.0, 185.0, 184.0], readings_per_week=1)
        result = trend_recommendation(self.athlete, self.target)
        self.assertEqual(result["action"], "check_adherence")

    def test_weekly_averages_shape(self):
        self._add_weights([186.0, 185.0])
        rows = weekly_averages(self.athlete, weeks=4)
        self.assertEqual(len(rows), 4)
        self.assertIsNotNone(rows[-1]["average"])
