from datetime import date

from django.test import TestCase

from core.tests.utils import make_exercise, make_program, make_user
from programs.models import WorkoutExercise
from workouts.models import SetLog, WorkoutSession
from workouts.services.history import session_completion


class SessionCompletionTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user()
        self.program = make_program(self.coach)
        self.day = self.program.weeks.first().days.first()
        self.required = self.day.exercises.get()
        self.optional = WorkoutExercise.objects.create(
            workout_day=self.day,
            exercise=make_exercise(),
            order=2,
            target_sets=3,
            optional=True,
        )
        self.session = WorkoutSession.objects.create(
            user=self.athlete,
            workout_day=self.day,
            program=self.program,
            date=date.today(),
        )

    def _log(self, prescription, set_number, **overrides):
        values = {
            "session": self.session,
            "workout_exercise": prescription,
            "exercise": prescription.exercise,
            "set_number": set_number,
            "completed": True,
        }
        values.update(overrides)
        return SetLog.objects.create(**values)

    def test_only_required_prescribed_working_sets_count(self):
        self._log(self.required, 1)
        self._log(self.required, 2, is_warmup=True)
        self._log(self.required, 2, is_extra=True)
        self._log(self.required, 4)  # Out of range even if the flag is malformed.
        for set_number in (1, 2, 3):
            self._log(self.optional, set_number)

        self.assertEqual(session_completion(self.session), (1, 3))

    def test_all_required_prescribed_sets_still_count_complete(self):
        for set_number in (1, 2, 3):
            self._log(self.required, set_number)

        self.assertEqual(session_completion(self.session), (3, 3))

    def test_session_without_a_day_has_no_prescribed_completion(self):
        standalone = WorkoutSession.objects.create(
            user=self.athlete,
            date=date.today(),
        )
        self.assertEqual(session_completion(standalone), (0, 0))
