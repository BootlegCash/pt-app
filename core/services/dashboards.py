"""Athlete dashboard summary assembly."""
from datetime import date as date_cls, timedelta


def athlete_dashboard_context(user):
    from calendar_app.models import ScheduledSession
    from profiles.models import AthleteProfile, Measurement
    from progress.models import LiftMax, PersonalRecord
    from workouts.models import WorkoutSession
    from workouts.services.history import weekly_adherence

    today = date_cls.today()
    profile = (
        AthleteProfile.objects.filter(user=user)
        .select_related("current_program", "coach")
        .first()
    )
    program = profile.current_program if profile else None
    todays_sessions = ScheduledSession.objects.filter(user=user, date=today)
    next_session = (
        ScheduledSession.objects.filter(
            user=user, date__gt=today, status=ScheduledSession.Status.SCHEDULED
        ).order_by("date", "order").first()
    )
    last_workout = WorkoutSession.objects.filter(
        user=user, status__in=["completed", "partial"]
    ).first()
    latest_pr = (
        PersonalRecord.objects.filter(user=user).select_related("exercise").first()
    )
    latest_max = LiftMax.objects.filter(user=user).select_related("exercise").first()
    weights = list(
        Measurement.objects.filter(user=user, bodyweight_lb__isnull=False)
        .values_list("date", "bodyweight_lb")[:5]
    )
    weight_trend = None
    if len(weights) >= 2:
        weight_trend = round(float(weights[0][1]) - float(weights[-1][1]), 1)
    adherence = weekly_adherence(user, weeks=1)[0]
    recent_readiness = [
        s.readiness_average
        for s in WorkoutSession.objects.filter(user=user)[:5]
        if s.readiness_average is not None
    ]
    readiness = (
        round(sum(recent_readiness) / len(recent_readiness), 1)
        if recent_readiness else None
    )
    return {
        "profile": profile,
        "program": program,
        "current_week": program.current_week_number() if program else None,
        "todays_sessions": todays_sessions,
        "next_session": next_session,
        "last_workout": last_workout,
        "latest_pr": latest_pr,
        "latest_max": latest_max,
        "bodyweight": weights[0] if weights else None,
        "weight_trend": weight_trend,
        "adherence": adherence,
        "readiness": readiness,
    }
