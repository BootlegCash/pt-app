from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from calendar_app.models import ScheduledSession
from core.tests.utils import (
    assign_program,
    link_coach,
    make_exercise,
    make_program,
    make_user,
)
from programs.models import Program
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
        new_start = date.today() - timedelta(days=7)

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
        self.assertTrue(
            ScheduledSession.objects.filter(
                user=athlete, program=program, date=new_start
            ).exists()
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


class ProgramAssignmentTests(TestCase):
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
