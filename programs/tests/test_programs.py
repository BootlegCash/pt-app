from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from calendar_app.models import ScheduledSession
from core.tests.utils import (
    assign_program,
    link_coach,
    make_admin,
    make_exercise,
    make_program,
    make_user,
)
from programs.models import Program
from programs.forms import WorkoutExerciseForm
from programs.services.copying import copy_program


class ProgramBuilderTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.client.force_login(self.coach)

    def test_create_program_creates_weeks(self):
        response = self.client.post(reverse("programs:builder_create"), {
            "name": "Block A", "description": "", "main_goal": "strength",
            "number_of_weeks": 3, "progression_enabled": "on",
            "client_visible_notes": "", "coach_notes": "",
        })
        program = Program.objects.get(name="Block A")
        self.assertRedirects(
            response, reverse("programs:builder_detail", args=[program.uuid])
        )
        self.assertEqual(program.weeks.count(), 3)
        self.assertEqual(program.status, Program.Status.DRAFT)

    def test_other_coach_cannot_open_program(self):
        program = make_program(self.coach)
        other = make_user(is_coach=True)
        self.client.force_login(other)
        response = self.client.get(
            reverse("programs:builder_detail", args=[program.uuid])
        )
        self.assertEqual(response.status_code, 403)

    def test_editing_start_date_updates_an_assigned_client_schedule(self):
        athlete = make_user()
        link_coach(self.coach, athlete)
        program = make_program(self.coach, weeks=1, days_per_week=2)
        assign_program(program, athlete, start_date=date.today())
        new_start = date.today() + timedelta(days=7)

        response = self.client.post(
            reverse("programs:builder_edit", args=[program.uuid]),
            {
                "name": program.name,
                "description": program.description,
                "main_goal": program.main_goal,
                "start_date": new_start.isoformat(),
                "number_of_weeks": program.number_of_weeks,
                "progression_enabled": "on",
                "client_visible_notes": program.client_visible_notes,
                "coach_notes": program.coach_notes,
            },
        )

        self.assertEqual(response.status_code, 302)
        program.refresh_from_db()
        athlete.athlete_profile.refresh_from_db()
        self.assertEqual(program.start_date, new_start)
        self.assertEqual(athlete.athlete_profile.program_start_date, new_start)
        expected_dates = {
            new_start + timedelta(
                days=(day.default_weekday - new_start.weekday()) % 7
            )
            for day in program.weeks.first().days.all()
        }
        actual_dates = set(
            ScheduledSession.objects.filter(
                user=athlete, program=program
            ).values_list("date", flat=True)
        )
        self.assertEqual(actual_dates, expected_dates)

    def test_editing_duration_creates_matching_week_records(self):
        program = make_program(self.coach, weeks=1, days_per_week=1)
        response = self.client.post(
            reverse("programs:builder_edit", args=[program.uuid]),
            {
                "name": program.name,
                "description": program.description,
                "main_goal": program.main_goal,
                "start_date": "",
                "number_of_weeks": 3,
                "progression_enabled": "on",
                "client_visible_notes": program.client_visible_notes,
                "coach_notes": program.coach_notes,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(program.weeks.order_by("week_number").values_list("week_number", flat=True)),
            [1, 2, 3],
        )

    def test_copy_program_produces_unassigned_draft(self):
        athlete = make_user()
        link_coach(self.coach, athlete)
        program = make_program(self.coach, weeks=2, days_per_week=2)
        assign_program(program, athlete)
        clone = copy_program(program, owner=self.coach)
        self.assertIsNone(clone.assigned_to)
        self.assertEqual(clone.status, Program.Status.DRAFT)
        self.assertEqual(clone.weeks.count(), 2)
        self.assertEqual(
            sum(week.days.count() for week in clone.weeks.all()), 4
        )
        original_exercise = program.weeks.first().days.first().exercises.first()
        cloned_exercise = clone.weeks.first().days.first().exercises.first()
        self.assertNotEqual(original_exercise.pk, cloned_exercise.pk)
        self.assertEqual(original_exercise.target_sets, cloned_exercise.target_sets)

    def test_exercise_edit_refreshes_assigned_calendar_type(self):
        athlete = make_user()
        link_coach(self.coach, athlete)
        running = make_exercise(name="Run", exercise_category="running")
        mobility = make_exercise(name="Mobility", exercise_category="mobility")
        program = make_program(self.coach, exercise=running)
        assign_program(program, athlete, start_date=date.today() + timedelta(days=1))
        prescription = program.weeks.first().days.first().exercises.first()
        scheduled = ScheduledSession.objects.get(program=program)
        self.assertEqual(scheduled.session_type, ScheduledSession.SessionType.RUNNING)

        response = self.client.post(
            reverse("programs:exercise_edit", args=[prescription.uuid]),
            {
                "exercise": mobility.id,
                "order": 1,
                "superset_group": "",
                "warmup_sets": 0,
                "target_sets": 3,
                "target_rep_min": 8,
                "target_rep_max": 12,
                "target_reps_text": "",
                "target_weight_lb": "",
                "set_weight_targets_text": "",
                "target_percentage": "",
                "target_rir": 2,
                "target_rpe": "",
                "tempo": "",
                "rest_seconds": "",
                "progression_method": "double",
                "weight_increment_lb": 5,
                "client_visible_notes": "",
                "private_coach_notes": "",
                "active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        scheduled.refresh_from_db()
        self.assertEqual(scheduled.session_type, ScheduledSession.SessionType.MOBILITY)


class ProgramExercisePrivacyTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.other_coach = make_user(is_coach=True)
        self.program = make_program(self.coach)
        self.day = self.program.weeks.first().days.first()
        self.public_exercise = make_exercise(name="Shared public exercise")
        self.own_private = make_exercise(
            name="Coach-owned private exercise",
            public=False,
            created_by=self.coach,
        )
        self.other_private = make_exercise(
            name="Other coach private exercise",
            public=False,
            created_by=self.other_coach,
        )
        self.inactive_public = make_exercise(
            name="Inactive public exercise",
            public=True,
            active=False,
        )

    def _exercise_ids(self, response):
        return set(
            response.context["form"].fields["exercise"].queryset.values_list(
                "id", flat=True
            )
        )

    def test_coach_create_and_edit_forms_hide_other_coach_private_exercise(self):
        self.client.force_login(self.coach)
        create_response = self.client.get(
            reverse("programs:exercise_create", args=[self.day.id])
        )
        prescription = self.day.exercises.first()
        edit_response = self.client.get(
            reverse("programs:exercise_edit", args=[prescription.uuid])
        )

        for response in (create_response, edit_response):
            exercise_ids = self._exercise_ids(response)
            self.assertIn(self.public_exercise.id, exercise_ids)
            self.assertIn(self.own_private.id, exercise_ids)
            self.assertNotIn(self.other_private.id, exercise_ids)
            self.assertNotIn(self.inactive_public.id, exercise_ids)

    def test_cross_coach_private_exercise_cannot_be_posted(self):
        self.client.force_login(self.coach)
        existing_count = self.day.exercises.count()
        response = self.client.post(
            reverse("programs:exercise_create", args=[self.day.id]),
            {
                "exercise": self.other_private.id,
                "order": 2,
                "superset_group": "",
                "warmup_sets": 0,
                "target_sets": 3,
                "target_rep_min": 8,
                "target_rep_max": 10,
                "target_reps_text": "",
                "target_weight_lb": "",
                "target_percentage": "",
                "target_rir": 2,
                "target_rpe": "",
                "tempo": "",
                "rest_seconds": "",
                "progression_method": "double",
                "weight_increment_lb": 5,
                "client_visible_notes": "",
                "private_coach_notes": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "exercise",
            "Select a valid choice. That choice is not one of the available choices.",
        )
        self.assertEqual(self.day.exercises.count(), existing_count)

    def test_staff_can_select_any_active_private_exercise(self):
        admin = make_admin()
        self.client.force_login(admin)
        response = self.client.get(
            reverse("programs:exercise_create", args=[self.day.id])
        )

        exercise_ids = self._exercise_ids(response)
        self.assertIn(self.own_private.id, exercise_ids)
        self.assertIn(self.other_private.id, exercise_ids)
        self.assertNotIn(self.inactive_public.id, exercise_ids)

    def test_per_set_weight_form_preserves_blank_positions(self):
        prescription = self.day.exercises.first()
        prescription.set_weight_targets_lb = [185, None, 205]
        prescription.save(update_fields=["set_weight_targets_lb"])
        form = WorkoutExerciseForm(instance=prescription, user=self.coach)
        self.assertEqual(form.fields["set_weight_targets_text"].initial, "185, , 205")

        data = {
            field: form.initial.get(field, "")
            for field in form.fields
            if field != "set_weight_targets_text"
        }
        data["exercise"] = prescription.exercise_id
        data["set_weight_targets_text"] = "185, , 205"
        bound = WorkoutExerciseForm(data=data, instance=prescription, user=self.coach)
        self.assertTrue(bound.is_valid(), bound.errors)
        saved = bound.save()
        self.assertEqual(saved.set_weight_targets_lb, [185.0, None, 205.0])


class ProgramAssignmentTests(TestCase):
    def test_program_detail_has_client_dropdown_and_assigns_in_place(self):
        coach = make_user(is_coach=True)
        athlete = make_user()
        athlete.first_name = "Client"
        athlete.last_name = "One"
        athlete.save(update_fields=["first_name", "last_name"])
        link_coach(coach, athlete)
        program = make_program(coach, weeks=1, days_per_week=1)
        self.client.force_login(coach)
        url = reverse("programs:builder_detail", args=[program.uuid])

        page = self.client.get(url)
        self.assertContains(page, "Choose a client")
        self.assertContains(page, "Client One")

        response = self.client.post(url, {
            "client": athlete.pk,
            "start_date": date.today().isoformat(),
        })

        self.assertRedirects(response, url)
        program.refresh_from_db()
        self.assertEqual(program.assigned_to, athlete)
        self.assertTrue(
            ScheduledSession.objects.filter(user=athlete, program=program).exists()
        )

    def test_program_detail_dropdown_rejects_unconnected_client(self):
        coach = make_user(is_coach=True)
        outsider = make_user()
        program = make_program(coach, weeks=1, days_per_week=1)
        self.client.force_login(coach)

        response = self.client.post(
            reverse("programs:builder_detail", args=[program.uuid]),
            {"client": outsider.pk, "start_date": date.today().isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        program.refresh_from_db()
        self.assertIsNone(program.assigned_to)

    def test_assignment_sets_profile_and_generates_calendar(self):
        coach, athlete = make_user(is_coach=True), make_user()
        link_coach(coach, athlete)
        program = make_program(coach, weeks=2, days_per_week=2)
        monday = date.today() - timedelta(days=date.today().weekday())
        assign_program(program, athlete, start_date=monday)

        program.refresh_from_db()
        self.assertEqual(program.status, Program.Status.ACTIVE)
        self.assertEqual(program.assigned_to, athlete)
        profile = athlete.athlete_profile
        profile.refresh_from_db()
        self.assertEqual(profile.current_program, program)
        self.assertEqual(profile.program_start_date, monday)
        sessions = ScheduledSession.objects.filter(user=athlete, program=program)
        self.assertEqual(sessions.count(), 4)  # 2 weeks × 2 days

    def test_reassignment_is_idempotent_for_scheduled_sessions(self):
        coach, athlete = make_user(is_coach=True), make_user()
        link_coach(coach, athlete)
        program = make_program(coach, weeks=1, days_per_week=3)
        assign_program(program, athlete)
        assign_program(program, athlete)
        self.assertEqual(
            ScheduledSession.objects.filter(user=athlete, program=program).count(), 3
        )

    def test_moving_start_forward_preserves_history_and_creates_new_future_day(self):
        from django.utils import timezone

        coach, athlete = make_user(is_coach=True), make_user()
        link_coach(coach, athlete)
        program = make_program(coach, weeks=1, days_per_week=1)
        today = timezone.localdate()
        old_start = today - timedelta(days=today.weekday() + 7)
        new_start = today + timedelta(days=(7 - today.weekday()))
        assign_program(program, athlete, start_date=old_start)
        day = program.weeks.first().days.first()
        old_session = ScheduledSession.objects.create(
            user=athlete,
            program=program,
            workout_day=day,
            date=old_start,
            title=day.name,
        )

        program.assign_to(athlete, assigned_by=coach, start_date=new_start)

        dates = set(
            ScheduledSession.objects.filter(program=program).values_list("date", flat=True)
        )
        self.assertEqual(dates, {old_session.date, new_start})

    def test_unassigned_weekdays_are_guessed_in_chronological_order(self):
        from django.utils import timezone

        coach, athlete = make_user(is_coach=True), make_user()
        link_coach(coach, athlete)
        program = make_program(coach, weeks=1, days_per_week=4)
        program.weeks.first().days.update(default_weekday=None)
        today = timezone.localdate()
        next_monday = today + timedelta(days=(7 - today.weekday()))

        assign_program(program, athlete, start_date=next_monday)

        schedule = list(
            ScheduledSession.objects.filter(program=program)
            .order_by("workout_day__day_number")
            .values_list("date", flat=True)
        )
        self.assertEqual(
            schedule,
            [
                next_monday,
                next_monday + timedelta(days=1),
                next_monday + timedelta(days=3),
                next_monday + timedelta(days=4),
            ],
        )

    def test_new_program_replaces_future_old_schedule_and_archives_old_program(self):
        coach, athlete = make_user(is_coach=True), make_user()
        link_coach(coach, athlete)
        old_program = make_program(coach, weeks=1, days_per_week=2)
        assign_program(old_program, athlete, start_date=date.today() + timedelta(days=1))
        old_session_ids = list(
            ScheduledSession.objects.filter(program=old_program).values_list("id", flat=True)
        )
        new_program = make_program(coach, weeks=1, days_per_week=1)

        assign_program(new_program, athlete, start_date=date.today() + timedelta(days=2))

        old_program.refresh_from_db()
        self.assertEqual(old_program.status, Program.Status.ARCHIVED)
        self.assertFalse(ScheduledSession.objects.filter(id__in=old_session_ids).exists())
        profile = athlete.athlete_profile
        profile.refresh_from_db()
        self.assertEqual(profile.current_program, new_program)
        self.assertIsNotNone(new_program.planned_end_date)

    def test_new_program_does_not_double_book_date_with_logged_old_workout(self):
        from workouts.models import WorkoutSession

        coach, athlete = make_user(is_coach=True), make_user()
        link_coach(coach, athlete)
        old_program = make_program(coach, weeks=1, days_per_week=1)
        assign_program(old_program, athlete, start_date=date.today())
        old_scheduled = ScheduledSession.objects.get(
            user=athlete, program=old_program
        )
        WorkoutSession.objects.create(
            user=athlete,
            scheduled_session=old_scheduled,
            workout_day=old_scheduled.workout_day,
            program=old_program,
            date=old_scheduled.date,
        )
        new_program = make_program(coach, weeks=1, days_per_week=1)

        assign_program(new_program, athlete, start_date=date.today())

        self.assertFalse(
            ScheduledSession.objects.filter(
                user=athlete,
                program=new_program,
                date=old_scheduled.date,
            ).exists()
        )
        self.assertTrue(
            ScheduledSession.objects.filter(pk=old_scheduled.pk).exists()
        )

    def test_new_program_avoids_date_with_unlinked_workout_history(self):
        from workouts.models import WorkoutSession

        coach, athlete = make_user(is_coach=True), make_user()
        link_coach(coach, athlete)
        old_program = make_program(coach, weeks=1, days_per_week=1)
        assign_program(old_program, athlete, start_date=date.today())
        old_scheduled = ScheduledSession.objects.get(
            user=athlete, program=old_program
        )
        WorkoutSession.objects.create(
            user=athlete,
            workout_day=old_scheduled.workout_day,
            program=old_program,
            date=old_scheduled.date,
        )
        new_program = make_program(coach, weeks=1, days_per_week=1)

        assign_program(new_program, athlete, start_date=date.today())

        self.assertFalse(
            ScheduledSession.objects.filter(
                user=athlete,
                program=new_program,
                date=old_scheduled.date,
            ).exists()
        )

    def test_program_cannot_be_stolen_from_another_client(self):
        coach = make_user(is_coach=True)
        first, second = make_user(), make_user()
        link_coach(coach, first)
        link_coach(coach, second)
        program = make_program(coach)
        assign_program(program, first)

        with self.assertRaisesMessage(ValueError, "already assigned"):
            assign_program(program, second)

        first.athlete_profile.refresh_from_db()
        self.assertEqual(first.athlete_profile.current_program, program)

    def test_assign_view_rejects_program_already_used_by_another_client(self):
        coach = make_user(is_coach=True)
        first, second = make_user(), make_user()
        link_coach(coach, first)
        link_coach(coach, second)
        program = make_program(coach)
        assign_program(program, first)
        self.client.force_login(coach)

        response = self.client.post(
            reverse("programs:builder_assign", args=[program.uuid, second.uuid]),
            {"start_date": date.today().isoformat()},
            follow=True,
        )

        self.assertContains(response, "already assigned to another client")
        program.refresh_from_db()
        self.assertEqual(program.assigned_to, first)

    def test_assign_view_requires_manage_permission(self):
        coach, athlete = make_user(is_coach=True), make_user()
        program = make_program(coach)
        self.client.force_login(coach)
        url = reverse("programs:builder_assign", args=[program.uuid, athlete.uuid])
        self.assertEqual(self.client.get(url).status_code, 403)  # no relationship
        link_coach(coach, athlete)
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"start_date": date.today().isoformat()})
        self.assertEqual(response.status_code, 302)
        program.refresh_from_db()
        self.assertEqual(program.assigned_to, athlete)


class WeekNumberTests(TestCase):
    def test_current_week_number(self):
        coach = make_user(is_coach=True)
        program = make_program(coach, weeks=4)
        program.start_date = date.today() - timedelta(days=15)
        self.assertEqual(program.current_week_number(), 3)
        program.start_date = date.today() + timedelta(days=3)
        self.assertIsNone(program.current_week_number())
