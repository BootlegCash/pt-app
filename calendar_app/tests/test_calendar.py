from datetime import date, timedelta

from django.test import TestCase

from calendar_app.models import ScheduledSession
from calendar_app.services.grids import month_grid, week_grid
from core.tests.utils import assign_program, link_coach, make_program, make_user


def monday_of(this_date):
    return this_date - timedelta(days=this_date.weekday())


class GenerationTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user()
        link_coach(self.coach, self.athlete)

    def test_days_land_on_default_weekdays(self):
        program = make_program(self.coach, weeks=2, days_per_week=2)
        start = monday_of(date.today())
        assign_program(program, self.athlete, start_date=start)
        sessions = list(
            ScheduledSession.objects.filter(user=self.athlete).order_by("date")
        )
        self.assertEqual(len(sessions), 4)
        # day 1 -> Monday (weekday 0), day 2 -> Tuesday (weekday 1)
        self.assertEqual(sessions[0].date, start)
        self.assertEqual(sessions[1].date, start + timedelta(days=1))
        self.assertEqual(sessions[2].date, start + timedelta(weeks=1))
        self.assertEqual(sessions[3].date, start + timedelta(weeks=1, days=1))

    def test_sessions_before_start_are_pulled_to_start(self):
        program = make_program(self.coach, weeks=1, days_per_week=2)
        wednesday = monday_of(date.today()) + timedelta(days=2)
        assign_program(program, self.athlete, start_date=wednesday)
        for session in ScheduledSession.objects.filter(user=self.athlete):
            self.assertGreaterEqual(session.date, wednesday)

    def test_effective_status_missed(self):
        session = ScheduledSession.objects.create(
            user=self.athlete, date=date.today() - timedelta(days=2),
            session_type="lifting", title="Old",
        )
        self.assertEqual(session.effective_status, ScheduledSession.Status.MISSED)
        session.status = ScheduledSession.Status.COMPLETED
        self.assertEqual(session.effective_status, ScheduledSession.Status.COMPLETED)

    def test_testing_week_sessions_marked_testing(self):
        program = make_program(self.coach, weeks=1, days_per_week=1)
        week = program.weeks.first()
        week.testing_week = True
        week.save()
        assign_program(program, self.athlete)
        session = ScheduledSession.objects.get(user=self.athlete)
        self.assertEqual(session.session_type, ScheduledSession.SessionType.TESTING)
        self.assertEqual(session.color_class, "cal-testing")


class GridTests(TestCase):
    def test_week_grid_has_seven_days_with_sessions(self):
        user = make_user()
        today = date.today()
        ScheduledSession.objects.create(
            user=user, date=today, session_type="lifting", title="Session A"
        )
        grid = week_grid(user, today)
        self.assertEqual(len(grid["days"]), 7)
        todays = [d for d in grid["days"] if d["date"] == today][0]
        self.assertEqual(len(todays["sessions"]), 1)
        self.assertTrue(todays["is_today"])

    def test_month_grid_covers_all_days(self):
        user = make_user()
        grid = month_grid(user, 2026, 7)
        cells = [cell for week in grid["weeks"] for cell in week if cell]
        self.assertEqual(len(cells), 31)

    def test_coach_can_add_move_delete_sessions_client_cannot(self):
        from django.urls import reverse

        coach, athlete = make_user(is_coach=True), make_user()
        link_coach(coach, athlete)
        self.client.force_login(coach)
        response = self.client.post(
            reverse("calendar_app:coach_session_create", args=[athlete.uuid]),
            {"date": date.today().isoformat(), "session_type": "mobility",
             "title": "Mobility 20 min", "notes": ""},
        )
        self.assertEqual(response.status_code, 302)
        session = ScheduledSession.objects.get(user=athlete)
        # client cannot edit or delete their schedule
        self.client.force_login(athlete)
        response = self.client.post(
            reverse("calendar_app:coach_session_delete", args=[session.uuid])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ScheduledSession.objects.filter(pk=session.pk).exists())
