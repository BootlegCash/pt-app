"""Measurement analysis helpers (trends, comparisons, Navy estimate)."""
import math


def measurement_changes(latest, previous):
    """Field-by-field change between two Measurement rows."""
    from .models import Measurement

    if latest is None:
        return []
    rows = []
    fields = ["bodyweight_lb"] + Measurement.CIRCUMFERENCE_FIELDS + ["estimated_body_fat"]
    for field in fields:
        current = getattr(latest, field, None)
        prior = getattr(previous, field, None) if previous else None
        change = None
        if current is not None and prior is not None:
            change = float(current) - float(prior)
        rows.append({
            "field": field,
            "label": field.replace("_lb", " (lb)").replace("_", " ").title(),
            "current": current,
            "previous": prior,
            "change": change,
        })
    return rows


def navy_body_fat_estimate(*, sex, height_inches, neck, waist, hips=None):
    """US Navy circumference method. Returns a ROUGH percentage estimate or None.

    This is presented to users as an estimate only — never as an exact value,
    and never as a muscle-mass claim.
    """
    try:
        height = float(height_inches)
        neck = float(neck)
        waist = float(waist)
    except (TypeError, ValueError):
        return None
    if height <= 0 or waist <= neck:
        return None
    if sex == "male":
        value = (
            86.010 * math.log10(waist - neck) - 70.041 * math.log10(height) + 36.76
        )
    elif sex == "female":
        if hips is None:
            return None
        value = (
            163.205 * math.log10(waist + float(hips) - neck)
            - 97.684 * math.log10(height) - 78.387
        )
    else:
        return None
    if value < 2 or value > 60:
        return None
    return round(value, 1)


def symmetry_pairs(measurement):
    """Left/right comparisons for the latest measurement."""
    pairs = [
        ("Arms", "left_arm", "right_arm"),
        ("Forearms", "left_forearm", "right_forearm"),
        ("Thighs", "left_thigh", "right_thigh"),
        ("Calves", "left_calf", "right_calf"),
    ]
    rows = []
    if measurement is None:
        return rows
    for label, left_field, right_field in pairs:
        left = getattr(measurement, left_field)
        right = getattr(measurement, right_field)
        diff = None
        if left is not None and right is not None:
            diff = float(right) - float(left)
        rows.append({"label": label, "left": left, "right": right, "diff": diff})
    return rows
