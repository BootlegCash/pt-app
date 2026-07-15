from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from core.tests.utils import make_program, make_user
from programs.services.prescriptions import (
    prescribed_weight_for_set,
    resolve_prescribed_weight,
)
from progress.models import LiftMax


class ResolvePrescribedWeightTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user()

    def _prescription(self, **kwargs):
        program = make_program(self.coach, **kwargs)
        return program.weeks.first().days.first().exercises.first()

    def test_explicit_weight_wins(self):
        prescription = self._prescription(target_weight_lb=Decimal("135"))
        result = resolve_prescribed_weight(prescription, self.athlete)
        self.assertEqual(result["source"], "explicit")
        self.assertEqual(result["weight"], Decimal("135"))

    def test_percentage_resolves_from_training_max_with_rounding(self):
        prescription = self._prescription(
            target_weight_lb=None, target_percentage=Decimal("72.5")
        )
        LiftMax.objects.create(
            user=self.athlete, exercise=prescription.exercise,
            max_type=LiftMax.MaxType.TRAINING, weight_lb=Decimal("300"),
            reps=1, date=date.today(),
        )
        result = resolve_prescribed_weight(prescription, self.athlete)
        self.assertEqual(result["source"], "percentage")
        # 72.5% of 300 = 217.5, already a multiple of 2.5
        self.assertEqual(result["weight"], 217.5)
        self.assertEqual(result["reference"].max_type, LiftMax.MaxType.TRAINING)

    def test_training_max_preferred_over_tested(self):
        prescription = self._prescription(
            target_weight_lb=None, target_percentage=Decimal("80")
        )
        LiftMax.objects.create(
            user=self.athlete, exercise=prescription.exercise,
            max_type=LiftMax.MaxType.TESTED, weight_lb=Decimal("315"),
            reps=1, date=date.today(),
        )
        LiftMax.objects.create(
            user=self.athlete, exercise=prescription.exercise,
            max_type=LiftMax.MaxType.TRAINING, weight_lb=Decimal("285"),
            reps=1, date=date.today() - timedelta(days=30),
        )
        result = resolve_prescribed_weight(prescription, self.athlete)
        self.assertEqual(result["reference"].max_type, LiftMax.MaxType.TRAINING)
        self.assertEqual(result["weight"], 227.5)  # 80% of 285 = 228 -> 227.5

    def test_no_max_on_file(self):
        prescription = self._prescription(
            target_weight_lb=None, target_percentage=Decimal("75")
        )
        result = resolve_prescribed_weight(prescription, self.athlete)
        self.assertIsNone(result["weight"])
        self.assertIsNone(result["source"])

    def test_per_set_weight_wins_then_falls_back_to_general_target(self):
        prescription = self._prescription(target_weight_lb=Decimal("135"))
        prescription.set_weight_targets_lb = [125, 130]
        self.assertEqual(
            prescribed_weight_for_set(prescription, self.athlete, 1), 125
        )
        self.assertEqual(
            prescribed_weight_for_set(prescription, self.athlete, 2), 130
        )
        self.assertEqual(
            prescribed_weight_for_set(prescription, self.athlete, 3), Decimal("135")
        )
