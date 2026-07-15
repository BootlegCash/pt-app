"""Week/month grid construction for calendar templates."""
import calendar as pycal
from datetime import date as date_cls, timedelta

from django.utils import timezone

from calendar_app.models import ScheduledSession


def week_grid(user, start):
    monday = start - timedelta(days=start.weekday())
    days = []
    sessions = ScheduledSession.objects.filter(
        user=user, date__range=(monday, monday + timedelta(days=6))
    ).select_related("workout_day", "program")
    by_date = {}
    for session in sessions:
        by_date.setdefault(session.date, []).append(session)
    today = timezone.localdate()
    for offset in range(7):
        day = monday + timedelta(days=offset)
        days.append({
            "date": day,
            "sessions": by_date.get(day, []),
            "is_today": day == today,
        })
    return {
        "days": days,
        "monday": monday,
        "prev_start": monday - timedelta(days=7),
        "next_start": monday + timedelta(days=7),
    }


def month_grid(user, year, month):
    first_weekday, days_in_month = pycal.monthrange(year, month)
    first = date_cls(year, month, 1)
    last = date_cls(year, month, days_in_month)
    sessions = ScheduledSession.objects.filter(
        user=user, date__range=(first, last)
    ).select_related("workout_day")
    by_date = {}
    for session in sessions:
        by_date.setdefault(session.date, []).append(session)
    today = timezone.localdate()
    weeks, current = [], []
    for _ in range(first_weekday):
        current.append(None)
    for day_number in range(1, days_in_month + 1):
        day = date_cls(year, month, day_number)
        current.append({
            "date": day,
            "sessions": by_date.get(day, []),
            "is_today": day == today,
        })
        if len(current) == 7:
            weeks.append(current)
            current = []
    if current:
        current.extend([None] * (7 - len(current)))
        weeks.append(current)
    prev_month = (first - timedelta(days=1)).replace(day=1)
    next_month = (last + timedelta(days=1)).replace(day=1)
    return {
        "weeks": weeks,
        "first": first,
        "prev": prev_month,
        "next": next_month,
        "month_name": first.strftime("%B %Y"),
    }
