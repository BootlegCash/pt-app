"""Coach-dashboard summaries."""
from datetime import timedelta

from django.utils import timezone

from coaching.models import CoachClientRelationship, ProgressionRecommendation


def active_clients(coach, include_all_for_admin=False):
    from accounts.models import User
    from core.services.access import is_administrator

    if include_all_for_admin and is_administrator(coach):
        return User.objects.filter(is_athlete=True, is_active=True)
    client_ids = CoachClientRelationship.objects.filter(
        coach=coach, status=CoachClientRelationship.Status.ACTIVE
    ).values_list("client_id", flat=True)
    return User.objects.filter(id__in=client_ids, is_active=True)


def client_summary(client):
    """One dashboard row for a client."""
    from calendar_app.models import ScheduledSession
    from imports.models import ImportJob
    from profiles.models import AthleteProfile, Measurement
    from progress.models import PersonalRecord
    from workouts.models import PainReport, WorkoutSession
    from workouts.services.history import weekly_adherence

    profile = AthleteProfile.objects.filter(user=client).select_related("current_program").first()
    today = timezone.localdate()
    last_workout = WorkoutSession.objects.filter(
        user=client, status__in=["completed", "partial"]
    ).first()
    next_scheduled = ScheduledSession.objects.filter(
        user=client, date__gte=today, status=ScheduledSession.Status.SCHEDULED
    ).order_by("date").first()
    week = weekly_adherence(client, weeks=1)[0]
    recent_prs = PersonalRecord.objects.filter(
        user=client, date__gte=today - timedelta(days=14)
    ).count()
    pain_flags = PainReport.objects.filter(
        session__user=client, reviewed_by_coach=False
    ).count()
    missed = sum(
        1 for s in ScheduledSession.objects.filter(
            user=client, date__gte=today - timedelta(days=14), date__lt=today
        ) if s.effective_status == ScheduledSession.Status.MISSED
    )
    pending_progressions = ProgressionRecommendation.objects.filter(
        user=client, status=ProgressionRecommendation.Status.PENDING
    ).count()
    pending_imports = ImportJob.objects.filter(
        user=client, status=ImportJob.Status.SUBMITTED
    ).count()
    recent_notes = WorkoutSession.objects.filter(
        user=client, date__gte=today - timedelta(days=7)
    ).exclude(notes="").count()
    latest_weights = list(
        Measurement.objects.filter(user=client, bodyweight_lb__isnull=False)
        .values_list("bodyweight_lb", flat=True)[:2]
    )
    weight_trend = None
    if len(latest_weights) == 2:
        weight_trend = float(latest_weights[0]) - float(latest_weights[1])
    return {
        "client": client,
        "profile": profile,
        "last_workout": last_workout,
        "next_scheduled": next_scheduled,
        "adherence": week,
        "recent_prs": recent_prs,
        "pain_flags": pain_flags,
        "missed": missed,
        "pending_progressions": pending_progressions,
        "pending_imports": pending_imports,
        "recent_notes": recent_notes,
        "weight_trend": weight_trend,
    }
