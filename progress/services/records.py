"""Personal-record detection and current-max summaries."""
from decimal import Decimal

from progress.models import LiftMax, PersonalRecord
from progress.services.one_rm import default_estimate


def _best_before(user, exercise, record_type, before_date):
    return (
        PersonalRecord.objects.filter(
            user=user, exercise=exercise, record_type=record_type, date__lt=before_date
        )
        .order_by("-value")
        .first()
    )


def _historic_best(user, exercise, session):
    """Best weight / e1RM / reps-at-weight from all sets BEFORE this session."""
    from workouts.models import SetLog

    logs = SetLog.objects.filter(
        session__user=user, exercise=exercise, completed=True, is_warmup=False,
        weight_lb__isnull=False, reps__isnull=False,
    ).exclude(session=session).select_related("session")
    best_weight, best_e1rm = 0.0, 0.0
    reps_at_weight = {}
    for log in logs:
        weight = float(log.weight_lb)
        best_weight = max(best_weight, weight)
        best_e1rm = max(best_e1rm, default_estimate(weight, log.reps))
        key = weight
        reps_at_weight[key] = max(reps_at_weight.get(key, 0), log.reps)
    return best_weight, best_e1rm, reps_at_weight


def detect_prs_for_session(session):
    """Create PersonalRecord rows for any bests set in this session.

    Called when a workout is completed. Idempotent per session: existing PRs
    linked to this session's sets are replaced.
    """
    user = session.user
    PersonalRecord.objects.filter(set_log__session=session).delete()
    created = []
    exercises = {
        log.exercise_id: log.exercise
        for log in session.set_logs.filter(
            completed=True, is_warmup=False,
            weight_lb__isnull=False, reps__isnull=False,
        ).select_related("exercise")
    }
    for exercise in exercises.values():
        best_weight, best_e1rm, reps_at_weight = _historic_best(user, exercise, session)
        session_logs = list(session.set_logs.filter(
            exercise=exercise, completed=True, is_warmup=False,
            weight_lb__isnull=False, reps__isnull=False,
        ))
        # Heaviest weight PR (requires prior history to compare against)
        top = max(session_logs, key=lambda log: float(log.weight_lb))
        if best_weight > 0 and float(top.weight_lb) > best_weight:
            created.append(PersonalRecord.objects.create(
                user=user, exercise=exercise,
                record_type=PersonalRecord.RecordType.WEIGHT,
                value=top.weight_lb, weight_lb=top.weight_lb, reps=top.reps,
                previous_value=Decimal(str(best_weight)),
                date=session.date, set_log=top,
            ))
        # Best estimated 1RM PR
        top_e1rm_log = max(
            session_logs, key=lambda log: default_estimate(float(log.weight_lb), log.reps)
        )
        session_e1rm = default_estimate(float(top_e1rm_log.weight_lb), top_e1rm_log.reps)
        if best_e1rm > 0 and session_e1rm > best_e1rm:
            created.append(PersonalRecord.objects.create(
                user=user, exercise=exercise,
                record_type=PersonalRecord.RecordType.E1RM,
                value=Decimal(str(round(session_e1rm, 1))),
                weight_lb=top_e1rm_log.weight_lb, reps=top_e1rm_log.reps,
                previous_value=Decimal(str(round(best_e1rm, 1))) if best_e1rm else None,
                date=session.date, set_log=top_e1rm_log,
            ))
        # Rep PR at a previously-used weight
        for log in session_logs:
            weight = float(log.weight_lb)
            previous_reps = reps_at_weight.get(weight)
            if previous_reps and log.reps > previous_reps:
                created.append(PersonalRecord.objects.create(
                    user=user, exercise=exercise,
                    record_type=PersonalRecord.RecordType.REPS,
                    value=log.reps, weight_lb=log.weight_lb, reps=log.reps,
                    previous_value=previous_reps,
                    date=session.date, set_log=log,
                ))
                reps_at_weight[weight] = log.reps
    return created


MAIN_LIFT_SLUGS = ["bench-press", "back-squat", "deadlift", "overhead-press"]


def current_maxes_summary(user, limit=6):
    """Latest max per exercise with previous-max comparison, newest first."""
    summaries = []
    seen = set()
    for lift_max in LiftMax.objects.filter(user=user).select_related("exercise"):
        if lift_max.exercise_id in seen:
            continue
        seen.add(lift_max.exercise_id)
        previous = (
            LiftMax.objects.filter(user=user, exercise=lift_max.exercise)
            .exclude(pk=lift_max.pk)
            .order_by("-date")
            .first()
        )
        change = None
        if previous and previous.best_value and lift_max.best_value:
            change = float(lift_max.best_value) - float(previous.best_value)
        summaries.append({
            "max": lift_max,
            "previous": previous,
            "change": change,
            "ratio": lift_max.bodyweight_ratio(),
        })
        if len(summaries) >= limit:
            break
    return summaries
