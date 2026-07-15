"""Generate ScheduledSession rows from an assigned program's weeks/days."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

def suggested_weekdays(day_count):
    """Return an evenly-spaced, chronological default training week."""
    patterns = {
        1: [0],
        2: [0, 3],
        3: [0, 2, 4],
        4: [0, 1, 3, 4],
        5: [0, 1, 2, 3, 4],
        6: [0, 1, 2, 3, 4, 5],
    }
    return patterns.get(day_count, list(range(7)))


def queue_google_deletions(athlete_id, event_ids):
    """Persist remote deletions without blocking the schedule-editing request."""
    from calendar_app.models import GoogleCalendarDeletion

    GoogleCalendarDeletion.objects.bulk_create(
        [
            GoogleCalendarDeletion(user_id=athlete_id, event_id=event_id)
            for event_id in event_ids
            if event_id
        ],
        ignore_conflicts=True,
    )


@transaction.atomic
def generate_program_schedule(
    program,
    athlete,
    *,
    replace_future=True,
    skip_past=False,
    avoid_dates_with_logged_workouts=False,
):
    """Create calendar entries for every workout day of `program`.

    Weeks are anchored to the exact start date. Existing future rows are
    updated in place so active workouts and Google event identifiers survive
    program edits. Dates before the athlete's current program week are not
    backfilled as false missed workouts.
    """
    from calendar_app.models import ScheduledSession
    from exercises.models import Exercise

    start = program.start_date
    if start is None:
        return []
    today = timezone.localdate()
    if today >= start:
        elapsed_weeks = (today - start).days // 7
        active_week_start = start + timedelta(weeks=elapsed_weeks)
    else:
        active_week_start = start

    existing_sessions = list(
        ScheduledSession.objects.filter(user=athlete, program=program)
        .prefetch_related("workout_sessions")
    )
    preserved_dates_by_day = {}
    linked_day_ids = set()
    for session in existing_sessions:
        if session.workout_day_id and session.workout_sessions.exists():
            linked_day_ids.add(session.workout_day_id)
        if session.workout_day_id and (
            session.date < today or session.workout_sessions.exists()
        ):
            preserved_dates_by_day.setdefault(session.workout_day_id, set()).add(
                session.date
            )
    occupied_dates = set()
    if avoid_dates_with_logged_workouts:
        from workouts.models import WorkoutSession

        occupied_dates = set(
            WorkoutSession.objects.filter(user=athlete)
            .exclude(program=program)
            .values_list("date", flat=True)
        )
    editable_by_day = {
        session.workout_day_id: session
        for session in existing_sessions
        if (
            replace_future
            and session.workout_day_id
            and session.status == ScheduledSession.Status.SCHEDULED
            and session.date >= today
            and not session.workout_sessions.exists()
        )
    }
    stale_candidates = {
        session.id: session
        for session in existing_sessions
        if (
            replace_future
            and session.status == ScheduledSession.Status.SCHEDULED
            and session.date >= today
            and not session.workout_sessions.exists()
        )
    }
    created = []
    weeks = program.weeks.filter(
        week_number__lte=program.number_of_weeks
    ).prefetch_related("days__exercises__exercise")
    for week in weeks:
        used_weekdays = set()
        days = list(week.days.all())
        fallback_weekdays = suggested_weekdays(len(days))
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
            weekday_offset = (weekday - start.weekday()) % 7
            session_date = (
                start
                + timedelta(weeks=week.week_number - 1)
                + timedelta(days=weekday_offset)
            )
            if session_date < active_week_start:
                continue
            if skip_past and session_date < today:
                continue
            if session_date in occupied_dates:
                continue
            if (
                day.id in linked_day_ids
                or session_date in preserved_dates_by_day.get(day.id, set())
            ):
                continue
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
            existing = editable_by_day.get(day.id)
            if existing:
                stale_candidates.pop(existing.id, None)
                new_values = {
                    "date": session_date,
                    "session_type": session_type,
                    "title": day.name,
                    "order": index,
                }
                changed = any(
                    getattr(existing, field) != value
                    for field, value in new_values.items()
                )
                if changed:
                    for field, value in new_values.items():
                        setattr(existing, field, value)
                    existing.google_synced_at = None
                    existing.save(update_fields=[*new_values, "google_synced_at"])
                continue
            created.append(ScheduledSession(
                user=athlete, date=session_date, session_type=session_type,
                title=day.name, program=program, workout_day=day, order=index,
            ))
    ScheduledSession.objects.bulk_create(created)
    stale = list(stale_candidates.values())
    removed_event_ids = [session.google_event_id for session in stale if session.google_event_id]
    if stale:
        ScheduledSession.objects.filter(id__in=[session.id for session in stale]).delete()
    if removed_event_ids:
        queue_google_deletions(athlete.id, removed_event_ids)
    return created
