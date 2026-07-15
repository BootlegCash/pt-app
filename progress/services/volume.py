"""Training-volume estimates. Muscle-group counts are labelled estimates —
compound lifts stimulate several muscles and no exact per-muscle stimulus is
claimed anywhere in the UI."""
from collections import Counter
from datetime import timedelta

from django.utils import timezone


def volume_summary(user, days=28):
    from workouts.models import SetLog

    since = timezone.localdate() - timedelta(days=days)
    logs = list(
        SetLog.objects.filter(
            session__user=user, completed=True, is_warmup=False,
            session__date__gte=since,
        ).select_related("exercise")
    )
    total_sets = len(logs)
    total_reps = sum(log.reps or 0 for log in logs)
    volume_load = round(sum(
        float(log.weight_lb) * log.reps
        for log in logs if log.weight_lb and log.reps
    ))
    by_muscle = Counter()
    by_pattern = Counter()
    by_exercise = Counter()
    for log in logs:
        exercise = log.exercise
        by_muscle[exercise.get_primary_muscle_display()] += 1
        for secondary in exercise.secondary_muscles or []:
            by_muscle[str(secondary).replace("_", " ").title()] += 0.5
        by_pattern[exercise.get_movement_pattern_display()] += 1
        by_exercise[exercise.name] += 1
    return {
        "days": days,
        "total_sets": total_sets,
        "total_reps": total_reps,
        "volume_load": volume_load,
        "sets_by_muscle": sorted(
            ((k, round(v, 1)) for k, v in by_muscle.items()),
            key=lambda kv: -kv[1],
        ),
        "sets_by_pattern": by_pattern.most_common(),
        "sets_by_exercise": by_exercise.most_common(15),
    }
