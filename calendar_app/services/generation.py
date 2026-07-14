"""Generate ScheduledSession rows from an assigned program's weeks/days."""
from datetime import timedelta

from django.db import transaction


def _week_monday(any_date):
    return any_date - timedelta(days=any_date.weekday())


@transaction.atomic
def generate_program_schedule(program, athlete, *, replace_future=True):
    """Create calendar entries for every workout day of `program`.

    Week 1 is anchored to the week containing start_date. Days with a
    default_weekday land on that weekday; days without one are spread across
    the week in order. Sessions earlier than start_date are pulled forward to
    start_date. Existing not-yet-completed sessions for this program are
    replaced so re-assignment is idempotent.
    """
    from calendar_app.models import ScheduledSession
    from exercises.models import Exercise

    start = program.start_date
    if start is None:
        return []
    if replace_future:
        ScheduledSession.objects.filter(
            user=athlete, program=program,
            status=ScheduledSession.Status.SCHEDULED,
        ).delete()

    anchor_monday = _week_monday(start)
    created = []
    fallback_weekdays = [0, 2, 4, 1, 3, 5, 6]  # Mon Wed Fri Tue Thu Sat Sun

    for week in program.weeks.prefetch_related("days__exercises__exercise"):
        week_monday = anchor_monday + timedelta(weeks=week.week_number - 1)
        used_weekdays = set()
        days = list(week.days.all())
        for index, day in enumerate(days):
            weekday = day.default_weekday
            if weekday is None:
                for candidate in fallback_weekdays:
                    if candidate not in used_weekdays:
                        weekday = candidate
                        break
                else:
                    weekday = index % 7
            used_weekdays.add(weekday)
            session_date = week_monday + timedelta(days=weekday)
            if session_date < start:
                session_date = start
            session_type = ScheduledSession.SessionType.LIFTING
            if week.testing_week:
                session_type = ScheduledSession.SessionType.TESTING
            else:
                categories = {
                    we.exercise.exercise_category for we in day.exercises.all()
                }
                if categories and categories <= {Exercise.Category.RUNNING, Exercise.Category.CONDITIONING}:
                    session_type = ScheduledSession.SessionType.RUNNING
                elif categories and categories <= {Exercise.Category.MOBILITY, Exercise.Category.WARMUP}:
                    session_type = ScheduledSession.SessionType.MOBILITY
            created.append(ScheduledSession(
                user=athlete,
                date=session_date,
                session_type=session_type,
                title=day.name,
                program=program,
                workout_day=day,
                order=index,
            ))
    ScheduledSession.objects.bulk_create(created)
    return created
