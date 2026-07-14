"""Calorie and macro calculation.

Energy expenditure uses Mifflin-St Jeor by default, or Katch-McArdle when a
reasonably reliable body-fat estimate exists. Every output is an ESTIMATE that
must be adjusted against real bodyweight trends — the UI says so explicitly.
Macro coefficients come from the active MacroRuleSet, not hardcoded values.
"""
from decimal import Decimal

LB_TO_KG = 0.45359237
IN_TO_CM = 2.54

ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "very": 1.725,
    "extreme": 1.9,
}

OCCUPATION_ADJUSTMENT = {
    "seated": 0.0,
    "mixed": 0.05,
    "standing": 0.1,
    "physical": 0.15,
}

PROTEIN_KCAL, CARB_KCAL, FAT_KCAL = 4, 4, 9


def mifflin_st_jeor_bmr(*, sex, weight_lb, height_inches, age):
    weight_kg = float(weight_lb) * LB_TO_KG
    height_cm = float(height_inches) * IN_TO_CM
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + (5 if sex == "male" else -161)


def katch_mcardle_bmr(*, weight_lb, body_fat_percent):
    lean_kg = float(weight_lb) * LB_TO_KG * (1 - float(body_fat_percent) / 100.0)
    return 370 + 21.6 * lean_kg


def estimate_tdee(
    *, bmr, activity_level, occupation_activity,
    weekly_lifting_days=0, weekly_cardio_days=0,
):
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.375)
    multiplier += OCCUPATION_ADJUSTMENT.get(occupation_activity, 0.0)
    # Small nudge for formal training volume beyond the base activity factor.
    multiplier += 0.01 * min(weekly_lifting_days + weekly_cardio_days, 7)
    return bmr * multiplier


def goal_adjustment(*, goal, tdee, ruleset, rate_lb_per_week=None):
    """(daily calorie delta, expected weekly change in lb)."""
    kcal_per_lb = float(ruleset.kcal_per_lb_weekly_change)
    if goal == "cut":
        rate = abs(float(rate_lb_per_week or 1.0))
        return -rate * kcal_per_lb, -rate
    if goal == "recomp":
        deficit = tdee * float(ruleset.recomp_deficit_percent) / 100.0
        return -deficit, round(-deficit / kcal_per_lb, 2)
    if goal == "maintain":
        return 0.0, 0.0
    if goal == "lean_bulk":
        rate = abs(float(rate_lb_per_week or 0.5))
        return rate * kcal_per_lb, rate
    if goal == "performance":
        surplus = float(ruleset.performance_surplus_kcal)
        return surplus, round(surplus / kcal_per_lb, 2)
    return 0.0, 0.0


def calculate_targets(
    *,
    sex,
    age,
    height_inches,
    weight_lb,
    activity_level,
    occupation_activity,
    weekly_lifting_days,
    weekly_cardio_days,
    goal,
    ruleset,
    rate_lb_per_week=None,
    body_fat_percent=None,
    calorie_adjustment=0,
    use_katch=False,
):
    """Full nutrition-target calculation. Returns a plain dict of integers."""
    if use_katch and body_fat_percent:
        bmr = katch_mcardle_bmr(weight_lb=weight_lb, body_fat_percent=body_fat_percent)
        method = "katch"
    else:
        bmr = mifflin_st_jeor_bmr(
            sex=sex, weight_lb=weight_lb, height_inches=height_inches, age=age
        )
        method = "mifflin"
    tdee = estimate_tdee(
        bmr=bmr, activity_level=activity_level,
        occupation_activity=occupation_activity,
        weekly_lifting_days=weekly_lifting_days,
        weekly_cardio_days=weekly_cardio_days,
    )
    delta, weekly_change = goal_adjustment(
        goal=goal, tdee=tdee, ruleset=ruleset, rate_lb_per_week=rate_lb_per_week
    )
    calories = max(1200.0, tdee + delta + float(calorie_adjustment or 0))

    protein_per_lb = (
        ruleset.protein_g_per_lb_cut if goal in ("cut", "recomp")
        else ruleset.protein_g_per_lb
    )
    protein_g = float(weight_lb) * float(protein_per_lb)
    fat_g = max(
        calories * float(ruleset.fat_percent_calories) / 100.0 / FAT_KCAL,
        float(weight_lb) * float(ruleset.fat_minimum_g_per_lb),
    )
    carbs_g = max(0.0, (calories - protein_g * PROTEIN_KCAL - fat_g * FAT_KCAL) / CARB_KCAL)
    fiber_g = calories / 1000.0 * float(ruleset.fiber_g_per_1000_kcal)
    water_oz = float(weight_lb) * float(ruleset.water_oz_per_lb)

    return {
        "method": method,
        "bmr": round(bmr),
        "maintenance_calories": round(tdee),
        "calories": round(calories),
        "protein_g": round(protein_g),
        "carbs_g": round(carbs_g),
        "fat_g": round(fat_g),
        "fiber_g": round(fiber_g),
        "water_oz": round(water_oz),
        "expected_weekly_change_lb": Decimal(str(weekly_change)),
        "warnings": _warnings(goal, rate_lb_per_week, weight_lb, ruleset),
    }


def _warnings(goal, rate_lb_per_week, weight_lb, ruleset):
    notes = [
        "Calorie targets are estimates. Adjust based on the real bodyweight "
        "trend over 2–4 weeks, not a single weigh-in.",
    ]
    if goal == "cut" and rate_lb_per_week and weight_lb:
        percent = abs(float(rate_lb_per_week)) / float(weight_lb) * 100
        if percent > float(ruleset.cut_max_weekly_loss_percent):
            notes.append(
                f"Requested loss rate is {percent:.1f}% of bodyweight per week — "
                f"above the configured {ruleset.cut_max_weekly_loss_percent}% "
                "guideline. Consider a slower rate."
            )
    return notes
