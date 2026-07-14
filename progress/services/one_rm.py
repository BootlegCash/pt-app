"""Estimated 1RM formulas. Epley and Brzycki are both supported; the displayed
default is configurable via the DEFAULT_E1RM_FORMULA environment variable."""
from django.conf import settings


def epley(weight, reps):
    if reps <= 0 or weight <= 0:
        return 0.0
    if reps == 1:
        return float(weight)
    return float(weight) * (1 + reps / 30.0)


def brzycki(weight, reps):
    if reps <= 0 or weight <= 0:
        return 0.0
    if reps == 1:
        return float(weight)
    if reps >= 37:  # formula breaks down; clamp
        reps = 36
    return float(weight) * 36.0 / (37.0 - reps)


def default_estimate(weight, reps):
    formula = getattr(settings, "DEFAULT_E1RM_FORMULA", "epley")
    return brzycki(weight, reps) if formula == "brzycki" else epley(weight, reps)


def both_estimates(weight, reps):
    return {
        "epley": round(epley(weight, reps), 1),
        "brzycki": round(brzycki(weight, reps), 1),
    }
