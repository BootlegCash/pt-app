"""Weekly bodyweight-trend analysis and calorie-adjustment recommendations.

Recommendations are advisory only: the coach applies (or ignores) them by
editing the nutrition target, which is audited. Nothing changes automatically.
"""
from datetime import date as date_cls, timedelta

from profiles.models import Measurement


def weekly_averages(user, weeks=6):
    """[(week_start, avg_bodyweight, n_readings)] oldest→newest."""
    today = date_cls.today()
    monday = today - timedelta(days=today.weekday())
    rows = []
    for offset in range(weeks - 1, -1, -1):
        start = monday - timedelta(weeks=offset)
        end = start + timedelta(days=6)
        weights = list(
            Measurement.objects.filter(
                user=user, date__range=(start, end), bodyweight_lb__isnull=False
            ).values_list("bodyweight_lb", flat=True)
        )
        average = round(sum(float(w) for w in weights) / len(weights), 1) if weights else None
        rows.append({"week_start": start, "average": average, "readings": len(weights)})
    return rows


def trend_recommendation(user, target):
    """Compare actual vs target weekly change and suggest a calorie adjustment."""
    rows = [r for r in weekly_averages(user, weeks=6) if r["average"] is not None]
    if len(rows) < 2:
        return {
            "action": "collect_data",
            "message": "Not enough weekly bodyweight data yet — continue collecting "
                       "weigh-ins before adjusting calories.",
            "actual_weekly_change": None,
        }
    recent = rows[-3:] if len(rows) >= 3 else rows
    deltas = [
        recent[i + 1]["average"] - recent[i]["average"]
        for i in range(len(recent) - 1)
    ]
    actual = round(sum(deltas) / len(deltas), 2)
    expected = float(target.expected_weekly_change_lb or 0) if target else 0.0
    gap = actual - expected
    sparse = any(r["readings"] < 3 for r in recent)
    if sparse:
        return {
            "action": "check_adherence",
            "message": "Few weigh-ins per week — confirm weigh-in and target adherence "
                       "before adjusting calories.",
            "actual_weekly_change": actual,
        }
    if abs(gap) <= 0.25:
        return {
            "action": "maintain",
            "message": f"Actual trend ({actual:+.2f} lb/wk) is close to the target "
                       f"({expected:+.2f} lb/wk). Maintain current calories.",
            "actual_weekly_change": actual,
        }
    if gap > 0:
        return {
            "action": "decrease",
            "amount": "100–150",
            "message": f"Gaining {gap:+.2f} lb/wk relative to target — consider "
                       "decreasing calories by 100–150.",
            "actual_weekly_change": actual,
        }
    return {
        "action": "increase",
        "amount": "100–150",
        "message": f"Losing {abs(gap):.2f} lb/wk more than targeted — consider "
                   "increasing calories by 100–150.",
        "actual_weekly_change": actual,
    }
