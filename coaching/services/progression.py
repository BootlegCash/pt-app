"""Progressive-overload recommendation engine.

Recommendations are generated when a workout completes. They are NEVER applied
automatically: a coach approves (applies), modifies, or rejects each one, and
every applied change produces an audit record.
"""
from decimal import Decimal

from django.utils import timezone

from coaching.models import ProgressionRecommendation
from core.services.audit import record_change
from programs.models import ProgressionMethod


def _performance_summary(logs):
    return ", ".join(
        f"{log.weight_lb:g}×{log.reps}"
        + (f" @RIR{log.rir:g}" if log.rir is not None else "")
        + (f" @RPE{log.rpe:g}" if log.rpe is not None else "")
        for log in logs if log.weight_lb is not None and log.reps is not None
    )


def _analyze(prescription, logs):
    """Return (action, amount, reasoning) for one prescription's completed sets."""
    method = prescription.progression_method
    increment = prescription.weight_increment_lb or Decimal("5")
    working = [log for log in logs if log.completed and not log.is_warmup]
    if not working:
        return None
    all_prescribed_done = len(working) >= prescription.target_sets
    rep_max = prescription.target_rep_max
    rep_min = prescription.target_rep_min
    reps = [log.reps for log in working if log.reps is not None]
    if not reps:
        return None
    any_failed = any(log.failed for log in working)

    def effort_ok():
        """True when no set exceeded the prescribed effort (RIR/RPE)."""
        ok = True
        for log in working:
            if prescription.target_rir is not None and log.rir is not None:
                if log.rir < prescription.target_rir:
                    ok = False
            if prescription.target_rpe is not None and log.rpe is not None:
                if log.rpe > prescription.target_rpe:
                    ok = False
        return ok

    if any_failed:
        return (
            ProgressionRecommendation.Action.REDUCE_WEIGHT, increment,
            "A set was recorded as failed — reduce the load and rebuild.",
        )

    if method == ProgressionMethod.DOUBLE:
        if rep_max and all_prescribed_done and min(reps) >= rep_max and effort_ok():
            return (
                ProgressionRecommendation.Action.ADD_WEIGHT, increment,
                f"All {prescription.target_sets} sets reached the top of the "
                f"{rep_min}–{rep_max} range at or above the target effort "
                f"(double progression).",
            )
        if rep_min and max(reps) < rep_min:
            return (
                ProgressionRecommendation.Action.REDUCE_WEIGHT, increment,
                f"Reps fell below the bottom of the {rep_min}–{rep_max} range.",
            )
        return (
            ProgressionRecommendation.Action.REPEAT, None,
            "Range not yet topped out — repeat the weight and add reps.",
        )

    if method == ProgressionMethod.FIXED_LOAD:
        if all_prescribed_done and (not rep_min or min(reps) >= (rep_min or 0)):
            return (
                ProgressionRecommendation.Action.ADD_WEIGHT, increment,
                f"Successful workout — fixed-load progression adds {increment:g} lb.",
            )
        return (
            ProgressionRecommendation.Action.REPEAT, None,
            "Not all prescribed sets were completed — repeat the load.",
        )

    if method == ProgressionMethod.REP:
        if all_prescribed_done:
            return (
                ProgressionRecommendation.Action.ADD_REP, None,
                "All prescribed sets completed — add one rep per set at the same weight.",
            )
        return (
            ProgressionRecommendation.Action.REPEAT, None,
            "Complete all prescribed sets before adding reps.",
        )

    if method == ProgressionMethod.RIR_RPE:
        if all_prescribed_done and effort_ok():
            return (
                ProgressionRecommendation.Action.ADD_WEIGHT, increment,
                "All sets completed without exceeding the target effort.",
            )
        return (
            ProgressionRecommendation.Action.IMPROVE_RIR, None,
            "Effort exceeded the target — keep the load and improve RIR first.",
        )

    if method == ProgressionMethod.PERCENTAGE:
        return (
            ProgressionRecommendation.Action.REPEAT, None,
            "Percentage-based prescription — loads follow the training max; "
            "review the training max if all sets were comfortable.",
        )

    if method == ProgressionMethod.PERFORMANCE:
        if rep_max and min(reps) >= rep_max and effort_ok():
            return (
                ProgressionRecommendation.Action.ADD_WEIGHT, increment,
                "Previous performance beat the target range — increase the load.",
            )
        if rep_min and max(reps) < rep_min:
            return (
                ProgressionRecommendation.Action.REDUCE_WEIGHT, increment,
                "Performance fell below the prescribed range — reduce the load.",
            )
        return (
            ProgressionRecommendation.Action.COLLECT_DATA, None,
            "Performance in range — continue collecting data before changing the load.",
        )

    return None  # MANUAL: the coach decides without system suggestions.


def generate_recommendations_for_session(session):
    """Create pending recommendations for each prescription trained in `session`."""
    if session.workout_day is None:
        return []
    program = session.workout_day.program_week.program
    if not program.progression_enabled:
        return []
    created = []
    logs_by_prescription = {}
    for log in session.set_logs.select_related("workout_exercise"):
        if log.workout_exercise_id:
            logs_by_prescription.setdefault(log.workout_exercise_id, []).append(log)
    for prescription in session.workout_day.exercises.filter(active=True):
        logs = logs_by_prescription.get(prescription.id)
        if not logs:
            continue
        result = _analyze(prescription, logs)
        if result is None:
            continue
        action, amount, reasoning = result
        # Only one pending recommendation per prescription at a time.
        ProgressionRecommendation.objects.filter(
            workout_exercise=prescription, user=session.user,
            status=ProgressionRecommendation.Status.PENDING,
        ).delete()
        created.append(ProgressionRecommendation.objects.create(
            user=session.user,
            workout_exercise=prescription,
            source_session=session,
            action=action,
            amount_lb=amount,
            reasoning=reasoning,
            previous_performance=_performance_summary(logs),
        ))
    return created


def apply_recommendation(recommendation, *, reviewed_by, modified_amount=None, note=""):
    """Approve and apply a recommendation to the prescription (audited)."""
    prescription = recommendation.workout_exercise
    amount = modified_amount if modified_amount is not None else recommendation.amount_lb
    action = recommendation.action
    previous_weight = prescription.target_weight_lb

    if action == ProgressionRecommendation.Action.ADD_WEIGHT and amount:
        prescription.target_weight_lb = (previous_weight or Decimal("0")) + amount
    elif action == ProgressionRecommendation.Action.REDUCE_WEIGHT and amount:
        new_weight = (previous_weight or Decimal("0")) - amount
        prescription.target_weight_lb = max(new_weight, Decimal("0"))
    elif action == ProgressionRecommendation.Action.ADD_REP:
        if prescription.target_rep_min:
            prescription.target_rep_min += 1
        if prescription.target_rep_max:
            prescription.target_rep_max += 1
    # REPEAT / IMPROVE_RIR / DELOAD / COLLECT_DATA change nothing numerically.
    prescription.save()

    if prescription.target_weight_lb != previous_weight:
        record_change(
            changed_by=reviewed_by, affected_user=recommendation.user,
            obj=prescription, field="target_weight_lb",
            previous=previous_weight, new=prescription.target_weight_lb,
            reason=f"Progression approval: {recommendation.get_action_display()}",
        )

    recommendation.status = (
        ProgressionRecommendation.Status.MODIFIED
        if modified_amount is not None and modified_amount != recommendation.amount_lb
        else ProgressionRecommendation.Status.APPROVED
    )
    recommendation.reviewed_by = reviewed_by
    recommendation.reviewed_at = timezone.now()
    recommendation.review_note = note
    recommendation.save()
    return recommendation


def reject_recommendation(recommendation, *, reviewed_by, note=""):
    recommendation.status = ProgressionRecommendation.Status.REJECTED
    recommendation.reviewed_by = reviewed_by
    recommendation.reviewed_at = timezone.now()
    recommendation.review_note = note
    recommendation.save()
    record_change(
        changed_by=reviewed_by, affected_user=recommendation.user,
        obj=recommendation.workout_exercise, field="progression",
        previous=recommendation.get_action_display(), new="rejected",
        reason="Progression recommendation rejected",
    )
    return recommendation
