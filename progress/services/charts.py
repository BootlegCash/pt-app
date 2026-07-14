"""Chart.js data builders. Each returns {"labels": [...], "datasets": [...]}-style
dicts consumed by static/js/charts.js."""
from collections import OrderedDict
from datetime import timedelta

from profiles.models import Measurement
from progress.services.one_rm import default_estimate


def bodyweight_chart(user):
    rows = list(
        Measurement.objects.filter(user=user, bodyweight_lb__isnull=False)
        .order_by("date")
        .values_list("date", "bodyweight_lb")
    )
    labels = [str(d) for d, _ in rows]
    weights = [float(w) for _, w in rows]
    # 7-day rolling average over recorded points
    averages = []
    for index, (day, _) in enumerate(rows):
        window = [
            float(w) for d, w in rows
            if day - timedelta(days=6) <= d <= day
        ]
        averages.append(round(sum(window) / len(window), 1) if window else None)
    return {
        "labels": labels,
        "series": [
            {"label": "Bodyweight (lb)", "data": weights},
            {"label": "7-day average", "data": averages},
        ],
    }


def measurement_chart(user, field):
    if field not in Measurement.CIRCUMFERENCE_FIELDS + ["estimated_body_fat"]:
        return {"labels": [], "series": []}
    rows = list(
        Measurement.objects.filter(user=user)
        .exclude(**{f"{field}__isnull": True})
        .order_by("date")
        .values_list("date", field)
    )
    return {
        "labels": [str(d) for d, _ in rows],
        "series": [{
            "label": field.replace("_", " ").title(),
            "data": [float(v) for _, v in rows],
        }],
    }


def e1rm_chart(user, exercise):
    from workouts.models import SetLog

    logs = SetLog.objects.filter(
        session__user=user, exercise=exercise, completed=True, is_warmup=False,
        weight_lb__isnull=False, reps__isnull=False,
    ).select_related("session").order_by("session__date")
    by_date = OrderedDict()
    for log in logs:
        value = default_estimate(float(log.weight_lb), log.reps)
        key = str(log.session.date)
        by_date[key] = max(by_date.get(key, 0), round(value, 1))
    return {
        "labels": list(by_date.keys()),
        "series": [{"label": f"{exercise.name} est. 1RM", "data": list(by_date.values())}],
    }


def adherence_chart(user, weeks=8):
    from workouts.services.history import weekly_adherence

    rows = weekly_adherence(user, weeks=weeks)
    return {
        "labels": [str(r["week_start"]) for r in rows],
        "series": [{
            "label": "Weekly completion %",
            "data": [r["percent"] if r["percent"] is not None else 0 for r in rows],
        }],
    }


def volume_chart(user, weeks=8):
    """Weekly volume load (sum of weight×reps on completed sets)."""
    from datetime import date as date_cls

    from workouts.models import SetLog

    today = date_cls.today()
    monday = today - timedelta(days=today.weekday())
    labels, data = [], []
    for offset in range(weeks - 1, -1, -1):
        start = monday - timedelta(weeks=offset)
        end = start + timedelta(days=6)
        logs = SetLog.objects.filter(
            session__user=user, completed=True, is_warmup=False,
            session__date__range=(start, end),
            weight_lb__isnull=False, reps__isnull=False,
        )
        labels.append(str(start))
        data.append(round(sum(float(l.weight_lb) * l.reps for l in logs)))
    return {"labels": labels, "series": [{"label": "Volume load (lb)", "data": data}]}


def readiness_chart(user, limit=20):
    from workouts.models import WorkoutSession

    sessions = list(
        WorkoutSession.objects.filter(user=user)
        .exclude(energy__isnull=True)
        .order_by("-date")[:limit]
    )[::-1]
    return {
        "labels": [str(s.date) for s in sessions],
        "series": [{
            "label": "Readiness (avg of 1–5 scores)",
            "data": [s.readiness_average for s in sessions],
        }],
    }


def running_pace_chart(user, limit=30):
    """Average pace (min/mile) for completed running sets with distance+time."""
    from exercises.models import Exercise
    from workouts.models import SetLog

    logs = list(
        SetLog.objects.filter(
            session__user=user, completed=True,
            exercise__exercise_category=Exercise.Category.RUNNING,
            distance_yards__isnull=False, duration_seconds__isnull=False,
        ).select_related("session").order_by("session__date")[:limit]
    )
    labels, data = [], []
    for log in logs:
        miles = float(log.distance_yards) / 1760.0
        if miles <= 0 or not log.duration_seconds:
            continue
        pace = (log.duration_seconds / 60.0) / miles
        labels.append(str(log.session.date))
        data.append(round(pace, 2))
    return {"labels": labels, "series": [{"label": "Pace (min/mile)", "data": data}]}


def pr_timeline_chart(user, limit=40):
    from progress.models import PersonalRecord

    records = list(
        PersonalRecord.objects.filter(user=user)
        .select_related("exercise").order_by("date")[:limit]
    )
    return {
        "labels": [str(r.date) for r in records],
        "series": [{
            "label": "PR value",
            "data": [float(r.value) for r in records],
            "points": [
                f"{r.exercise.name} — {r.get_record_type_display()}" for r in records
            ],
        }],
    }
