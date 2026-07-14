"""Resolve what a prescription actually asks the athlete to lift.

Percentage-based prescriptions are resolved against the athlete's most
relevant recorded max (training max preferred), rounded to the nearest
2.5 lb. Explicit weights always win.
"""

MAX_TYPE_PRIORITY = ["training", "coach", "tested", "estimated", "rep_max"]
ROUND_TO_LB = 2.5


def reference_max_for(user, exercise):
    """The max a percentage prescription should key off, or None."""
    from progress.models import LiftMax

    for max_type in MAX_TYPE_PRIORITY:
        lift_max = (
            LiftMax.objects.filter(user=user, exercise=exercise, max_type=max_type)
            .order_by("-date", "-created_at")
            .first()
        )
        if lift_max and lift_max.best_value:
            return lift_max
    return None


def resolve_prescribed_weight(prescription, user):
    """{'weight': Decimal|float|None, 'source': 'explicit'|'percentage'|None,
        'reference': LiftMax|None} for display in the logger and day detail."""
    if prescription.target_weight_lb is not None:
        return {"weight": prescription.target_weight_lb, "source": "explicit", "reference": None}
    if prescription.target_percentage:
        reference = reference_max_for(user, prescription.exercise)
        if reference:
            raw = float(prescription.target_percentage) / 100.0 * float(reference.best_value)
            rounded = round(raw / ROUND_TO_LB) * ROUND_TO_LB
            return {"weight": rounded, "source": "percentage", "reference": reference}
    return {"weight": None, "source": None, "reference": None}


def prescribed_weight_for_set(prescription, user, set_number):
    """Return the editable default for one working set."""
    targets = prescription.set_weight_targets_lb or []
    index = set_number - 1
    if 0 <= index < len(targets) and targets[index] not in (None, ""):
        return targets[index]
    return resolve_prescribed_weight(prescription, user)["weight"]
