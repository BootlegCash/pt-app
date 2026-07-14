"""Previous/best performance lookups shown in the logger and day detail."""
from django.db.models import Max

from workouts.models import SetLog, WorkoutSession


def previous_exercise_performance(user, exercise, before_session=None):
    """Most recent completed sets of `exercise`, grouped as one session summary."""
    logs = SetLog.objects.filter(
        session__user=user, exercise=exercise, completed=True, is_warmup=False,
    ).select_related("session").order_by("-session__date", "set_number")
    if before_session is not None:
        logs = logs.exclude(session=before_session)
    first = logs.first()
    if first is None:
        return None
    session = first.session
    sets = [log for log in logs if log.session_id == session.id]
    return {
        "date": session.date,
        "sets": sets,
        "summary": ", ".join(
            f"{log.weight_lb:g}×{log.reps}" if log.weight_lb and log.reps else "—"
            for log in sets[:6]
        ),
    }


def best_exercise_performance(user, exercise):
    """Best completed set by estimated 1RM (falls back to heaviest weight)."""
    logs = SetLog.objects.filter(
        session__user=user, exercise=exercise, completed=True, is_warmup=False,
        weight_lb__isnull=False,
    )
    best, best_value = None, -1.0
    for log in logs:
        value = log.estimated_1rm or float(log.weight_lb)
        if value > best_value:
            best, best_value = log, value
    return best


def previous_day_performance(user, workout_day):
    """Map prescription id -> previous performance for a whole workout day."""
    if workout_day is None:
        return {}
    result = {}
    for prescription in workout_day.exercises.select_related("exercise"):
        result[prescription.id] = previous_exercise_performance(
            user, prescription.exercise
        )
    return result


def exercise_history(user, exercise):
    """Everything the exercise-history page needs."""
    from progress.models import LiftMax
    from progress.services.one_rm import brzycki, epley

    logs = list(
        SetLog.objects.filter(
            session__user=user, exercise=exercise, completed=True, is_warmup=False,
        ).select_related("session").order_by("session__date", "set_number")
    )
    sessions = {}
    for log in logs:
        sessions.setdefault(log.session_id, {"date": log.session.date, "sets": []})
        sessions[log.session_id]["sets"].append(log)
    best_set = best_exercise_performance(user, exercise)
    tested = (
        LiftMax.objects.filter(user=user, exercise=exercise, max_type=LiftMax.MaxType.TESTED)
        .order_by("-date").first()
    )
    trend = []
    for data in sessions.values():
        best_value = None
        for log in data["sets"]:
            if log.weight_lb and log.reps:
                value = epley(float(log.weight_lb), log.reps)
                if best_value is None or value > best_value:
                    best_value = value
        if best_value:
            trend.append({"date": str(data["date"]), "e1rm": round(best_value, 1)})
    return {
        "sessions": sorted(sessions.values(), key=lambda item: item["date"], reverse=True),
        "total_sessions": len(sessions),
        "best_set": best_set,
        "best_e1rm_epley": round(epley(float(best_set.weight_lb), best_set.reps), 1)
        if best_set and best_set.weight_lb and best_set.reps else None,
        "best_e1rm_brzycki": round(brzycki(float(best_set.weight_lb), best_set.reps), 1)
        if best_set and best_set.weight_lb and best_set.reps else None,
        "tested_max": tested,
        "trend": trend,
    }


def session_completion(session):
    """(completed_sets, prescribed_sets) for a session against its day template."""
    prescribed = 0
    if session.workout_day:
        prescribed = sum(
            we.target_sets for we in session.workout_day.exercises.filter(
                active=True, optional=False
            )
        )
    completed = session.set_logs.filter(completed=True, is_warmup=False).count()
    return completed, prescribed


def weekly_adherence(user, weeks=4):
    """Completed vs scheduled trainable sessions for recent weeks."""
    from datetime import date as date_cls, timedelta

    from calendar_app.models import ScheduledSession

    today = date_cls.today()
    monday = today - timedelta(days=today.weekday())
    rows = []
    for offset in range(weeks - 1, -1, -1):
        start = monday - timedelta(weeks=offset)
        end = start + timedelta(days=6)
        scheduled = ScheduledSession.objects.filter(
            user=user, date__range=(start, end),
            session_type__in=["lifting", "running", "mobility", "testing"],
        )
        total = scheduled.count()
        done = sum(
            1 for s in scheduled
            if s.effective_status in ("completed", "partial")
        )
        rows.append({
            "week_start": start,
            "scheduled": total,
            "completed": done,
            "percent": round(done * 100 / total) if total else None,
        })
    return rows
