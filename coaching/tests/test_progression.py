from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from coaching.models import ProgressionRecommendation
from coaching.services.progression import generate_recommendations_for_session
from core.models import AuditRecord
from core.tests.utils import assign_program, link_coach, make_program, make_user
from workouts.models import SetLog, WorkoutSession


def build_session(coach, athlete, *, method, sets=3, rep_min=8, rep_max=12,
                  weight=100, rir=Decimal("2"), performed=None):
    """Create a completed session with `performed` = [(weight, reps, rir, failed)]."""
    program = make_program(
        coach, progression_method=method,
        target_sets=sets, target_rep_min=rep_min, target_rep_max=rep_max,
        target_weight_lb=Decimal(weight), target_rir=rir,
    )
    assign_program(program, athlete)
    day = program.weeks.first().days.first()
    prescription = day.exercises.first()
    session = WorkoutSession.objects.create(
        user=athlete, workout_day=day, program=program,
        date=date.today(), status="completed",
    )
    for number, (set_weight, reps, set_rir, failed) in enumerate(performed, start=1):
        SetLog.objects.create(
            session=session, workout_exercise=prescription,
            exercise=prescription.exercise, set_number=number,
            weight_lb=Decimal(set_weight), reps=reps,
            rir=set_rir, failed=failed, completed=True,
        )
    return session, prescription


class RecommendationEngineTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user()
        link_coach(self.coach, self.athlete)

    def _recommend(self, **kwargs):
        session, prescription = build_session(self.coach, self.athlete, **kwargs)
        recommendations = generate_recommendations_for_session(session)
        return recommendations, prescription

    def test_double_progression_tops_range_adds_weight(self):
        recs, _ = self._recommend(
            method="double",
            performed=[(100, 12, Decimal("2"), False)] * 3,
        )
        self.assertEqual(recs[0].action, ProgressionRecommendation.Action.ADD_WEIGHT)
        self.assertEqual(recs[0].amount_lb, Decimal("5"))

    def test_double_progression_mid_range_repeats(self):
        recs, _ = self._recommend(
            method="double",
            performed=[(100, 10, Decimal("2"), False)] * 3,
        )
        self.assertEqual(recs[0].action, ProgressionRecommendation.Action.REPEAT)

    def test_double_progression_below_range_reduces(self):
        recs, _ = self._recommend(
            method="double",
            performed=[(100, 6, Decimal("0"), False)] * 3,
        )
        self.assertEqual(recs[0].action, ProgressionRecommendation.Action.REDUCE_WEIGHT)

    def test_failed_set_recommends_reduction(self):
        recs, _ = self._recommend(
            method="fixed_load",
            performed=[(100, 12, None, False), (100, 8, None, True)],
        )
        self.assertEqual(recs[0].action, ProgressionRecommendation.Action.REDUCE_WEIGHT)

    def test_fixed_load_success_adds_weight(self):
        recs, _ = self._recommend(
            method="fixed_load",
            performed=[(100, 8, None, False)] * 3,
        )
        self.assertEqual(recs[0].action, ProgressionRecommendation.Action.ADD_WEIGHT)

    def test_rep_progression_adds_rep(self):
        recs, _ = self._recommend(
            method="rep",
            performed=[(100, 10, None, False)] * 3,
        )
        self.assertEqual(recs[0].action, ProgressionRecommendation.Action.ADD_REP)

    def test_rir_gate_blocks_increase_when_effort_exceeded(self):
        recs, _ = self._recommend(
            method="rir_rpe",
            performed=[(100, 10, Decimal("0"), False)] * 3,  # target RIR 2, hit RIR 0
        )
        self.assertEqual(recs[0].action, ProgressionRecommendation.Action.IMPROVE_RIR)

    def test_rir_gate_allows_increase_at_target_effort(self):
        recs, _ = self._recommend(
            method="rir_rpe",
            performed=[(100, 10, Decimal("2"), False)] * 3,
        )
        self.assertEqual(recs[0].action, ProgressionRecommendation.Action.ADD_WEIGHT)

    def test_manual_method_generates_nothing(self):
        recs, _ = self._recommend(
            method="manual",
            performed=[(100, 10, None, False)] * 3,
        )
        self.assertEqual(recs, [])

    def test_progression_disabled_generates_nothing(self):
        session, _ = build_session(
            self.coach, self.athlete, method="double",
            performed=[(100, 12, Decimal("2"), False)] * 3,
        )
        session.workout_day.program_week.program.progression_enabled = False
        session.workout_day.program_week.program.save()
        self.assertEqual(generate_recommendations_for_session(session), [])


class ApprovalWorkflowTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user()
        link_coach(self.coach, self.athlete)
        session, self.prescription = build_session(
            self.coach, self.athlete, method="double",
            performed=[(100, 12, Decimal("2"), False)] * 3,
        )
        self.recommendation = generate_recommendations_for_session(session)[0]

    def test_prescription_unchanged_until_approved(self):
        self.prescription.refresh_from_db()
        self.assertEqual(self.prescription.target_weight_lb, Decimal("100"))

    def test_approve_applies_change_and_audits(self):
        self.client.force_login(self.coach)
        response = self.client.post(
            reverse("coaching:progression_approve", args=[self.recommendation.uuid]),
            {"note": "good work"},
        )
        self.assertEqual(response.status_code, 302)
        self.prescription.refresh_from_db()
        self.assertEqual(self.prescription.target_weight_lb, Decimal("105"))
        self.recommendation.refresh_from_db()
        self.assertEqual(self.recommendation.status, ProgressionRecommendation.Status.APPROVED)
        self.assertTrue(AuditRecord.objects.filter(
            affected_user=self.athlete, field_changed="target_weight_lb",
        ).exists())

    def test_modified_amount(self):
        self.client.force_login(self.coach)
        self.client.post(
            reverse("coaching:progression_approve", args=[self.recommendation.uuid]),
            {"modified_amount": "2.5"},
        )
        self.prescription.refresh_from_db()
        self.assertEqual(self.prescription.target_weight_lb, Decimal("102.5"))
        self.recommendation.refresh_from_db()
        self.assertEqual(self.recommendation.status, ProgressionRecommendation.Status.MODIFIED)

    def test_reject_changes_nothing(self):
        self.client.force_login(self.coach)
        self.client.post(
            reverse("coaching:progression_reject", args=[self.recommendation.uuid]),
            {"note": "hold"},
        )
        self.prescription.refresh_from_db()
        self.assertEqual(self.prescription.target_weight_lb, Decimal("100"))
        self.recommendation.refresh_from_db()
        self.assertEqual(self.recommendation.status, ProgressionRecommendation.Status.REJECTED)

    def test_athlete_cannot_approve_own_recommendation(self):
        self.client.force_login(self.athlete)
        response = self.client.post(
            reverse("coaching:progression_approve", args=[self.recommendation.uuid])
        )
        self.assertEqual(response.status_code, 403)
        self.prescription.refresh_from_db()
        self.assertEqual(self.prescription.target_weight_lb, Decimal("100"))
