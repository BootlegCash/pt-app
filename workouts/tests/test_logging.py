import json
from datetime import date

from django.test import TestCase
from django.urls import reverse

from calendar_app.models import ScheduledSession
from core.tests.utils import assign_program, link_coach, make_program, make_user
from progress.models import PersonalRecord
from progress.services.one_rm import both_estimates, brzycki, epley
from progress.services.records import detect_prs_for_session
from workouts.models import SetLog, WorkoutSession


class OneRmTests(TestCase):
    def test_epley_known_values(self):
        self.assertAlmostEqual(epley(200, 1), 200.0)
        self.assertAlmostEqual(epley(200, 5), 200 * (1 + 5 / 30))
        self.assertEqual(epley(0, 5), 0.0)

    def test_brzycki_known_values(self):
        self.assertAlmostEqual(brzycki(200, 1), 200.0)
        self.assertAlmostEqual(brzycki(225, 5), 225 * 36 / 32)
        self.assertGreater(brzycki(100, 36), 0)  # clamped, no division blowup

    def test_both_estimates(self):
        result = both_estimates(315, 3)
        self.assertIn("epley", result)
        self.assertIn("brzycki", result)


class LoggingFlowTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user()
        link_coach(self.coach, self.athlete)
        program = make_program(self.coach, weeks=1, days_per_week=1)
        assign_program(program, self.athlete)
        self.scheduled = ScheduledSession.objects.get(user=self.athlete)
        self.prescription = self.scheduled.workout_day.exercises.first()
        self.client.force_login(self.athlete)

    def _start_session(self):
        self.client.post(reverse("workouts:start", args=[self.scheduled.uuid]), {
            "energy": 4, "sleep_quality": 4, "soreness": 2, "stress": 1, "motivation": 5,
        })
        return WorkoutSession.objects.get(user=self.athlete)

    def _autosave(self, session, **overrides):
        payload = {
            "prescription": str(self.prescription.uuid), "set_number": 1,
            "weight": 100, "reps": 10, "rir": 2, "completed": True,
        }
        payload.update(overrides)
        return self.client.post(
            reverse("workouts:autosave", args=[session.uuid]),
            data=json.dumps(payload), content_type="application/json",
        )

    def test_start_records_readiness(self):
        session = self._start_session()
        self.assertEqual(session.energy, 4)
        self.assertEqual(session.status, WorkoutSession.Status.IN_PROGRESS)

    def test_logger_prefills_editable_per_set_weights(self):
        self.prescription.set_weight_targets_lb = [95, 105, 110]
        self.prescription.warmup_sets = 2
        self.prescription.save(update_fields=["set_weight_targets_lb", "warmup_sets"])
        session = self._start_session()
        response = self.client.get(reverse("workouts:logger", args=[session.uuid]))
        self.assertContains(response, 'value="95"')
        self.assertContains(response, 'value="105"')
        self.assertContains(response, 'value="110"')
        self.assertContains(response, 'title="Warm-up set 1"')
        self.assertContains(response, 'title="Working set 1"')

    def test_logged_weight_overrides_prescribed_default(self):
        self.prescription.set_weight_targets_lb = [95, 105, 110]
        self.prescription.save(update_fields=["set_weight_targets_lb"])
        session = self._start_session()
        self._autosave(session, set_number=1, weight=102.5)
        response = self.client.get(reverse("workouts:logger", args=[session.uuid]))
        self.assertContains(response, 'value="102.5"')

    def test_blank_per_set_target_stays_blank_instead_of_falling_back(self):
        self.prescription.set_weight_targets_lb = [95, None, 110]
        self.prescription.save(update_fields=["set_weight_targets_lb"])
        session = self._start_session()

        response = self.client.get(reverse("workouts:logger", args=[session.uuid]))

        weights = [row["weight"] for row in response.context["cards"][0]["rows"]]
        self.assertEqual(weights, [95, None, 110])

    def test_logger_calculates_percentage_weight_from_max(self):
        from datetime import date
        from progress.models import LiftMax

        self.prescription.target_weight_lb = None
        self.prescription.set_weight_targets_lb = []
        self.prescription.target_percentage = 80
        self.prescription.save(update_fields=[
            "target_weight_lb", "set_weight_targets_lb", "target_percentage",
        ])
        LiftMax.objects.create(
            user=self.athlete, exercise=self.prescription.exercise,
            max_type=LiftMax.MaxType.COACH, weight_lb=200, reps=1, date=date.today(),
        )
        session = self._start_session()
        response = self.client.get(reverse("workouts:logger", args=[session.uuid]))
        self.assertContains(response, 'value="160.0"')

    def test_strength_rep_text_still_uses_reps_and_effort_inputs(self):
        self.prescription.target_rep_min = None
        self.prescription.target_rep_max = None
        self.prescription.target_reps_text = "10 each"
        self.prescription.save(update_fields=[
            "target_rep_min", "target_rep_max", "target_reps_text",
        ])
        session = self._start_session()

        response = self.client.get(reverse("workouts:logger", args=[session.uuid]))

        self.assertContains(response, 'data-field="reps"')
        self.assertContains(response, 'data-field="rir"')
        self.assertNotContains(response, 'aria-label="Set 1 distance (yards)"')

    def test_autosave_upserts_single_row(self):
        session = self._start_session()
        self.assertEqual(self._autosave(session).status_code, 200)
        self.assertEqual(self._autosave(session, weight=105).status_code, 200)
        logs = SetLog.objects.filter(session=session)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(float(logs.first().weight_lb), 105.0)

    def test_autosave_rejects_foreign_session(self):
        session = self._start_session()
        intruder = make_user()
        self.client.force_login(intruder)
        self.assertEqual(self._autosave(session).status_code, 404)

    def test_autosave_rejects_prescription_from_other_day(self):
        session = self._start_session()
        other_program = make_program(self.coach)
        other_prescription = other_program.weeks.first().days.first().exercises.first()
        response = self._autosave(session, prescription=str(other_prescription.uuid))
        self.assertEqual(response.status_code, 400)

    def test_autosave_marks_extra_sets(self):
        session = self._start_session()
        self._autosave(session, set_number=4)  # target_sets is 3
        log = SetLog.objects.get(session=session, set_number=4)
        self.assertTrue(log.is_extra)

    def test_warmup_and_working_set_with_same_number_are_distinct(self):
        session = self._start_session()
        self._autosave(session, is_warmup=True, weight=45, reps=10)
        self._autosave(session, is_warmup=False, weight=100, reps=8)
        logs = SetLog.objects.filter(session=session, set_number=1)
        self.assertEqual(logs.count(), 2)
        self.assertEqual(float(logs.get(is_warmup=True).weight_lb), 45.0)
        self.assertEqual(float(logs.get(is_warmup=False).weight_lb), 100.0)

    def test_autosave_records_rpe_separately_from_rir(self):
        session = self._start_session()
        self._autosave(session, rir="", rpe=8.5)
        log = SetLog.objects.get(session=session, set_number=1)
        self.assertIsNone(log.rir)
        self.assertEqual(float(log.rpe), 8.5)

    def test_remove_extra_set_only(self):
        session = self._start_session()
        self._autosave(session, set_number=1)
        self._autosave(session, set_number=4)
        normal = SetLog.objects.get(session=session, set_number=1)
        extra = SetLog.objects.get(session=session, set_number=4)
        url = reverse("workouts:remove_extra_set", args=[session.uuid])
        self.assertEqual(self.client.post(url, {"set_uuid": normal.uuid}).status_code, 404)
        self.assertEqual(self.client.post(url, {"set_uuid": extra.uuid}).status_code, 200)
        self.assertFalse(SetLog.objects.filter(pk=extra.pk).exists())

    def test_complete_marks_statuses_and_generates_recommendation(self):
        session = self._start_session()
        for number in (1, 2, 3):
            self._autosave(session, set_number=number, reps=12)
        response = self.client.post(reverse("workouts:complete", args=[session.uuid]), {
            "session_difficulty": 7, "pump_rating": 4, "performance_rating": 4, "notes": "",
            "pain-body_location": "", "pain-severity": "", "pain-pain_type": "aching",
            "pain-notes": "",
        })
        self.assertEqual(response.status_code, 302)
        session.refresh_from_db()
        self.assertEqual(session.status, WorkoutSession.Status.COMPLETED)
        self.scheduled.refresh_from_db()
        self.assertEqual(self.scheduled.status, ScheduledSession.Status.COMPLETED)
        self.assertEqual(session.progression_recommendations.count(), 1)

    def test_partial_completion(self):
        session = self._start_session()
        self._autosave(session, set_number=1)
        self.client.post(reverse("workouts:complete", args=[session.uuid]), {
            "notes": "", "pain-body_location": "", "pain-severity": "",
            "pain-pain_type": "aching", "pain-notes": "",
        })
        session.refresh_from_db()
        self.assertEqual(session.status, WorkoutSession.Status.PARTIAL)

    def test_pain_report_flagged_for_coach(self):
        session = self._start_session()
        self._autosave(session)
        response = self.client.post(reverse("workouts:complete", args=[session.uuid]), {
            "notes": "", "had_pain": "on",
            "pain-body_location": "left knee", "pain-severity": 4,
            "pain-pain_type": "sharp", "pain-affected_performance": "on",
            "pain-notes": "on squats",
        })
        self.assertEqual(response.status_code, 302)
        report = session.pain_reports.get()
        self.assertFalse(report.reviewed_by_coach)
        self.client.force_login(self.coach)
        response = self.client.get(reverse("coaching:pain_flags"))
        self.assertContains(response, "left knee")


class PrDetectionTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user()
        link_coach(self.coach, self.athlete)
        self.program = make_program(self.coach)
        assign_program(self.program, self.athlete)
        self.day = self.program.weeks.first().days.first()
        self.prescription = self.day.exercises.first()
        self.exercise = self.prescription.exercise

    def _session_with_set(self, weight, reps, days_offset=0):
        from datetime import timedelta

        session = WorkoutSession.objects.create(
            user=self.athlete, workout_day=self.day, program=self.program,
            date=date.today() + timedelta(days=days_offset), status="completed",
        )
        SetLog.objects.create(
            session=session, workout_exercise=self.prescription,
            exercise=self.exercise, set_number=1,
            weight_lb=weight, reps=reps, completed=True,
        )
        return session

    def test_first_session_sets_no_prs(self):
        session = self._session_with_set(100, 8)
        self.assertEqual(len(detect_prs_for_session(session)), 0)

    def test_weight_e1rm_and_rep_prs(self):
        self._session_with_set(100, 8, days_offset=-7)
        session = self._session_with_set(110, 8)
        records = detect_prs_for_session(session)
        types = {record.record_type for record in records}
        self.assertIn(PersonalRecord.RecordType.WEIGHT, types)
        self.assertIn(PersonalRecord.RecordType.E1RM, types)
        # rep PR at the same weight
        session3 = self._session_with_set(110, 10, days_offset=7)
        types3 = {r.record_type for r in detect_prs_for_session(session3)}
        self.assertIn(PersonalRecord.RecordType.REPS, types3)

    def test_detection_is_idempotent(self):
        self._session_with_set(100, 8, days_offset=-7)
        session = self._session_with_set(120, 8)
        detect_prs_for_session(session)
        detect_prs_for_session(session)
        self.assertEqual(
            PersonalRecord.objects.filter(set_log__session=session).count(), 2
        )
