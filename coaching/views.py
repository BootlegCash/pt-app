from datetime import date as date_cls

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.services import create_user_account
from calendar_app.services.grids import month_grid, week_grid
from core.services.access import (
    get_client_or_404,
    is_administrator,
    is_coach,
)
from core.services.audit import record_change, record_form_changes
from profiles.forms import AthleteProfileForm, MeasurementForm
from profiles.models import AthleteProfile, Measurement
from progress.models import LiftMax, PersonalRecord
from progress.services.records import current_maxes_summary
from workouts.models import PainReport, WorkoutSession

from .forms import CreateUserForm, LiftMaxForm, PrivateNotesForm, ReviewForm
from .models import CoachClientRelationship, ProgressionRecommendation
from .services.clients import active_clients, client_summary
from .services.progression import apply_recommendation, reject_recommendation


def _coach_only(user):
    if not is_coach(user):
        raise PermissionDenied


@login_required
def dashboard(request):
    _coach_only(request.user)
    clients = active_clients(request.user, include_all_for_admin=True)
    summaries = [client_summary(client) for client in clients]
    from imports.models import ImportJob
    from programs.models import Program

    pending_imports = sum(s["pending_imports"] for s in summaries)
    pending_progressions = sum(s["pending_progressions"] for s in summaries)
    pain_flags = sum(s["pain_flags"] for s in summaries)
    stale_programs = Program.objects.filter(
        owner=request.user, status=Program.Status.ACTIVE,
        planned_end_date__lt=timezone.localdate(),
    ).count()
    relationships = {
        relationship.client_id: relationship
        for relationship in CoachClientRelationship.objects.filter(
            coach=request.user,
            status=CoachClientRelationship.Status.ACTIVE,
            client__in=clients,
        )
    }
    for summary in summaries:
        summary["relationship"] = relationships.get(summary["client"].id)
    return render(request, "coaching/dashboard.html", {
        "summaries": summaries,
        "active_client_count": len(summaries),
        "attention_count": pending_imports + pending_progressions + pain_flags,
        "pending_imports": pending_imports,
        "pending_progressions": pending_progressions,
        "pain_flags": pain_flags,
        "stale_programs": stale_programs,
    })


@login_required
def client_list(request):
    _coach_only(request.user)
    clients = active_clients(request.user, include_all_for_admin=True)
    return render(request, "coaching/client_list.html", {"clients": clients})


@login_required
def client_detail(request, client_uuid):
    client = get_client_or_404(request.user, client_uuid)
    summary = client_summary(client)
    relationship = CoachClientRelationship.objects.filter(
        coach=request.user, client=client
    ).first()
    notes_form = PrivateNotesForm(
        initial={"private_notes": relationship.private_notes if relationship else ""}
    )
    return render(request, "coaching/client_detail.html", {
        "client": client,
        "summary": summary,
        "relationship": relationship,
        "notes_form": notes_form,
        "maxes": current_maxes_summary(client, limit=8),
        "recent_sessions": WorkoutSession.objects.filter(user=client)[:8],
        "pending_recommendations": ProgressionRecommendation.objects.filter(
            user=client, status=ProgressionRecommendation.Status.PENDING
        ).select_related("workout_exercise__exercise")[:10],
    })


@login_required
@require_POST
def client_notes_save(request, client_uuid):
    client = get_client_or_404(request.user, client_uuid, manage=True)
    relationship = CoachClientRelationship.objects.filter(
        coach=request.user, client=client,
        status=CoachClientRelationship.Status.ACTIVE,
    ).first()
    if relationship is None:
        raise PermissionDenied("Notes require an active coaching relationship.")
    form = PrivateNotesForm(request.POST)
    if form.is_valid():
        relationship.private_notes = form.cleaned_data["private_notes"]
        relationship.save(update_fields=["private_notes"])
        messages.success(request, "Private notes saved.")
    return redirect("coaching:client_detail", client_uuid=client.uuid)


@login_required
def client_profile_edit(request, client_uuid):
    client = get_client_or_404(request.user, client_uuid, manage=True)
    profile, _ = AthleteProfile.objects.get_or_create(user=client)
    form = AthleteProfileForm(
        request.POST or None, request.FILES or None, instance=profile
    )
    if request.method == "POST" and form.is_valid():
        record_form_changes(
            changed_by=request.user, affected_user=client,
            form=form, reason="Profile edit",
        )
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("coaching:client_detail", client_uuid=client.uuid)
    return render(request, "coaching/client_profile_edit.html", {
        "client": client, "form": form,
    })


@login_required
def client_measurements(request, client_uuid):
    client = get_client_or_404(request.user, client_uuid, manage=True)
    form = MeasurementForm(request.POST or None, initial={"date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        measurement = form.save(commit=False)
        measurement.user = client
        measurement.entered_by = request.user
        measurement.save()
        if measurement.bodyweight_lb:
            profile, _ = AthleteProfile.objects.get_or_create(user=client)
            profile.current_weight_lb = measurement.bodyweight_lb
            profile.save(update_fields=["current_weight_lb", "updated_at"])
        record_change(
            changed_by=request.user, affected_user=client, obj=measurement,
            field="measurement", previous="", new=str(measurement.date),
            reason="Measurement entry",
        )
        messages.success(request, "Measurement recorded.")
        return redirect("coaching:client_measurements", client_uuid=client.uuid)
    return render(request, "coaching/client_measurements.html", {
        "client": client,
        "form": form,
        "measurements": Measurement.objects.filter(user=client)[:50],
    })


@login_required
def client_maxes(request, client_uuid):
    client = get_client_or_404(request.user, client_uuid, manage=True)
    form = LiftMaxForm(request.POST or None, initial={"date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        lift_max = form.save(commit=False)
        lift_max.user = client
        lift_max.entered_by = request.user
        lift_max.save()
        record_change(
            changed_by=request.user, affected_user=client, obj=lift_max,
            field="max", previous="",
            new=f"{lift_max.exercise.name} {lift_max.weight_lb}×{lift_max.reps}",
            reason="Max entry",
        )
        messages.success(request, "Max recorded.")
        return redirect("coaching:client_maxes", client_uuid=client.uuid)
    return render(request, "coaching/client_maxes.html", {
        "client": client,
        "form": form,
        "maxes": LiftMax.objects.filter(user=client).select_related("exercise")[:50],
        "summaries": current_maxes_summary(client, limit=10),
    })


@login_required
def client_calendar(request, client_uuid):
    client = get_client_or_404(request.user, client_uuid)
    view = request.GET.get("view", "week")
    today = timezone.localdate()
    if view == "month":
        try:
            year = int(request.GET.get("year", today.year))
            month = int(request.GET.get("month", today.month))
            date_cls(year, month, 1)
        except ValueError:
            year, month = today.year, today.month
        return render(request, "calendar_app/month.html", {
            "grid": month_grid(client, year, month),
            "athlete": client, "manage": True,
        })
    from datetime import datetime

    try:
        start = datetime.strptime(request.GET.get("start", ""), "%Y-%m-%d").date()
    except ValueError:
        start = today
    return render(request, "calendar_app/week.html", {
        "grid": week_grid(client, start),
        "athlete": client, "manage": True,
    })


@login_required
def client_history(request, client_uuid):
    client = get_client_or_404(request.user, client_uuid)
    sessions = WorkoutSession.objects.filter(user=client).select_related(
        "workout_day", "program"
    )[:100]
    return render(request, "coaching/client_history.html", {
        "client": client, "sessions": sessions,
    })


@login_required
def client_session_detail(request, client_uuid, session_uuid):
    client = get_client_or_404(request.user, client_uuid)
    session = get_object_or_404(
        WorkoutSession.objects.prefetch_related("set_logs__exercise", "pain_reports"),
        uuid=session_uuid, user=client,
    )
    grouped = {}
    for log in session.set_logs.select_related("exercise").order_by("exercise_id", "set_number"):
        grouped.setdefault(log.exercise, []).append(log)
    prs = PersonalRecord.objects.filter(set_log__session=session).select_related("exercise")
    return render(request, "workouts/detail.html", {
        "session": session,
        "grouped": grouped.items(),
        "prs": prs,
        "pain_reports": session.pain_reports.all(),
        "coach_view": True,
        "client": client,
    })


# --------------------------------------------------------------- approvals

@login_required
def progression_approvals(request):
    _coach_only(request.user)
    recommendations = ProgressionRecommendation.objects.filter(
        status=ProgressionRecommendation.Status.PENDING
    ).select_related("user", "workout_exercise__exercise", "source_session")
    if not is_administrator(request.user):
        client_ids = CoachClientRelationship.objects.filter(
            coach=request.user, status=CoachClientRelationship.Status.ACTIVE
        ).values_list("client_id", flat=True)
        recommendations = recommendations.filter(user_id__in=client_ids)
    return render(request, "coaching/progression_approvals.html", {
        "recommendations": recommendations,
        "review_form": ReviewForm(),
    })


def _get_reviewable(request, rec_uuid):
    recommendation = get_object_or_404(
        ProgressionRecommendation, uuid=rec_uuid,
        status=ProgressionRecommendation.Status.PENDING,
    )
    get_client_or_404(request.user, recommendation.user.uuid, manage=True)
    return recommendation


@login_required
@require_POST
def progression_approve(request, rec_uuid):
    recommendation = _get_reviewable(request, rec_uuid)
    form = ReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a positive weight adjustment.")
        return redirect("coaching:progression_approvals")
    apply_recommendation(
        recommendation,
        reviewed_by=request.user,
        modified_amount=form.cleaned_data.get("modified_amount"),
        note=form.cleaned_data.get("note", ""),
    )
    messages.success(request, "Recommendation applied to the prescription.")
    return redirect("coaching:progression_approvals")


@login_required
@require_POST
def progression_reject(request, rec_uuid):
    recommendation = _get_reviewable(request, rec_uuid)
    form = ReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, "The review could not be saved.")
        return redirect("coaching:progression_approvals")
    reject_recommendation(
        recommendation, reviewed_by=request.user, note=form.cleaned_data.get("note", "")
    )
    messages.info(request, "Recommendation rejected.")
    return redirect("coaching:progression_approvals")


@login_required
def pain_flags(request):
    _coach_only(request.user)
    reports = PainReport.objects.filter(reviewed_by_coach=False).select_related(
        "session__user", "exercise"
    )
    if not is_administrator(request.user):
        client_ids = CoachClientRelationship.objects.filter(
            coach=request.user, status=CoachClientRelationship.Status.ACTIVE
        ).values_list("client_id", flat=True)
        reports = reports.filter(session__user_id__in=client_ids)
    return render(request, "coaching/pain_flags.html", {"reports": reports})


@login_required
@require_POST
def pain_mark_reviewed(request, report_uuid):
    report = get_object_or_404(PainReport, uuid=report_uuid)
    get_client_or_404(request.user, report.session.user.uuid, manage=True)
    report.reviewed_by_coach = True
    report.save(update_fields=["reviewed_by_coach"])
    messages.success(request, "Pain report marked as reviewed.")
    return redirect("coaching:pain_flags")


# ----------------------------------------------------- administrator actions

@login_required
def create_user(request):
    if not is_administrator(request.user):
        raise PermissionDenied
    form = CreateUserForm(request.POST or None)
    created = None
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        user, password = create_user_account(
            username=data["username"], email=data["email"],
            first_name=data.get("first_name", ""), last_name=data.get("last_name", ""),
            is_coach=data.get("is_coach", False),
            is_athlete=data.get("is_athlete", True),
            temporary_password=data.get("temporary_password") or None,
            active=data.get("active", True),
            coach=data.get("coach"),
            created_by=request.user,
        )
        created = {"user": user, "password": password}
        messages.success(
            request,
            f"Account created for {user.username}. Share the temporary password "
            "securely — they must change it at first login.",
        )
        form = CreateUserForm()
    return render(request, "coaching/create_user.html", {"form": form, "created": created})


@login_required
@require_POST
def relationship_end(request, relationship_uuid):
    if not is_administrator(request.user):
        raise PermissionDenied
    relationship = get_object_or_404(CoachClientRelationship, uuid=relationship_uuid)
    relationship.status = CoachClientRelationship.Status.ENDED
    relationship.save()
    record_change(
        changed_by=request.user, affected_user=relationship.client, obj=relationship,
        field="status", previous="active", new="ended",
        reason="Coach-client relationship ended",
    )
    messages.info(request, "Relationship ended.")
    return redirect("coaching:client_list")
