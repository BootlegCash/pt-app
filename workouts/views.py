import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from calendar_app.models import ScheduledSession
from exercises.models import Exercise
from progress.services.records import detect_prs_for_session

from .forms import PainReportForm, ReadinessForm, WrapUpForm
from .models import SetLog, WorkoutSession
from .services.history import (
    best_exercise_performance,
    exercise_history,
    previous_day_performance,
    session_completion,
)


@login_required
def start_session(request, scheduled_uuid):
    """Readiness check-in, then create (or resume) the workout session."""
    scheduled = get_object_or_404(
        ScheduledSession.objects.select_related("workout_day", "program"),
        uuid=scheduled_uuid, user=request.user,
    )
    existing = WorkoutSession.objects.filter(
        user=request.user, scheduled_session=scheduled
    ).first()
    if existing:
        return redirect("workouts:logger", session_uuid=existing.uuid)
    form = ReadinessForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        session = form.save(commit=False)
        session.user = request.user
        session.scheduled_session = scheduled
        session.workout_day = scheduled.workout_day
        session.program = scheduled.program
        session.date = timezone.localdate()
        session.save()
        if session.pain_today:
            messages.info(
                request,
                "You reported pain today — please add details at the end of "
                "the workout so your coach can review them.",
            )
        return redirect("workouts:logger", session_uuid=session.uuid)
    return render(request, "workouts/start.html", {
        "scheduled": scheduled, "form": form,
    })


DISTANCE_CATEGORIES = {"running", "conditioning"}


@login_required
def logger(request, session_uuid):
    """Mobile-first logging screen. Set data autosaves; refresh loses nothing."""
    from programs.services.prescriptions import (
        prescribed_weight_for_set,
        resolve_prescribed_weight,
    )

    session = get_object_or_404(
        WorkoutSession.objects.select_related(
            "workout_day__program_week__program", "scheduled_session"
        ),
        uuid=session_uuid, user=request.user,
    )
    prescriptions = []
    if session.workout_day:
        prescriptions = list(
            session.workout_day.exercises.filter(active=True)
            .select_related("exercise")
        )
    existing_logs = {}
    for log in session.set_logs.all():
        existing_logs.setdefault(log.workout_exercise_id, []).append(log)
    previous = previous_day_performance(request.user, session.workout_day)
    cards = []
    for prescription in prescriptions:
        logs = existing_logs.get(prescription.id, [])
        working = [log for log in logs if not log.is_warmup]
        warmups = {log.set_number: log for log in logs if log.is_warmup}
        logged_numbers = {log.set_number for log in working}
        planned = max(prescription.target_sets, max(logged_numbers, default=0))
        by_number = {log.set_number: log for log in working}
        rows = []
        for number in range(1, planned + 1):
            log = by_number.get(number)
            weight = (
                log.weight_lb
                if log is not None and log.weight_lb is not None
                else prescribed_weight_for_set(prescription, request.user, number)
            )
            rows.append({"number": number, "log": log, "weight": weight})
        warmup_rows = [
            {
                "number": number,
                "log": warmups.get(number),
                "weight": warmups[number].weight_lb if number in warmups else None,
            }
            for number in range(1, prescription.warmup_sets + 1)
        ]
        substitution = next(
            (log.substitution_request for log in logs if log.substitution_request), ""
        )
        resolved = resolve_prescribed_weight(prescription, request.user)
        cards.append({
            "prescription": prescription,
            "rows": rows,
            "warmup_rows": warmup_rows,
            "previous": previous.get(prescription.id),
            "best": best_exercise_performance(request.user, prescription.exercise),
            "track_distance": (
                prescription.exercise.exercise_category in DISTANCE_CATEGORIES
            ),
            "substitution": substitution,
            "resolved": resolved,
        })
    return render(request, "workouts/logger.html", {
        "session": session,
        "cards": cards,
    })


def _decimal_or_none(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _int_or_none(value):
    if value in (None, ""):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


@login_required
@require_POST
def autosave_set(request, session_uuid):
    """Upsert one set from the logger. Returns save state for the UI."""
    session = get_object_or_404(
        WorkoutSession, uuid=session_uuid, user=request.user
    )
    if session.status != WorkoutSession.Status.IN_PROGRESS:
        return JsonResponse({"ok": False, "error": "Workout is already completed."}, status=400)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)

    from programs.models import WorkoutExercise

    prescription = get_object_or_404(
        WorkoutExercise.objects.select_related("exercise", "workout_day"),
        uuid=payload.get("prescription", ""),
    )
    if session.workout_day_id != prescription.workout_day_id:
        return JsonResponse({"ok": False, "error": "Exercise not in this workout."}, status=400)
    set_number = _int_or_none(payload.get("set_number"))
    if not set_number or set_number > 30:
        return JsonResponse({"ok": False, "error": "Invalid set number."}, status=400)
    is_warmup = bool(payload.get("is_warmup"))

    with transaction.atomic():
        log, _created = SetLog.objects.select_for_update().get_or_create(
            session=session,
            workout_exercise=prescription,
            exercise=prescription.exercise,
            set_number=set_number,
            is_warmup=is_warmup,
            defaults={
                "is_extra": not is_warmup and set_number > prescription.target_sets,
            },
        )
        log.weight_lb = _decimal_or_none(payload.get("weight"))
        log.reps = _int_or_none(payload.get("reps"))
        log.rir = _decimal_or_none(payload.get("rir"))
        log.rpe = _decimal_or_none(payload.get("rpe"))
        log.distance_yards = _decimal_or_none(payload.get("distance"))
        log.duration_seconds = _int_or_none(payload.get("duration"))
        log.completed = bool(payload.get("completed"))
        log.failed = bool(payload.get("failed"))
        log.notes = str(payload.get("notes", ""))[:300]
        log.substitution_request = str(payload.get("substitution", ""))[:200]
        log.full_clean(exclude=["session", "workout_exercise", "exercise"])
        log.save()
    return JsonResponse({"ok": True, "set_uuid": str(log.uuid)})


@login_required
@require_POST
def remove_extra_set(request, session_uuid):
    """Remove an extra (beyond-prescription) set only."""
    session = get_object_or_404(WorkoutSession, uuid=session_uuid, user=request.user)
    set_uuid = request.POST.get("set_uuid", "")
    log = get_object_or_404(SetLog, uuid=set_uuid, session=session, is_extra=True)
    log.delete()
    return JsonResponse({"ok": True})


@login_required
def complete_session(request, session_uuid):
    """End-of-workout wrap-up: feedback, optional pain report, PR detection."""
    session = get_object_or_404(
        WorkoutSession, uuid=session_uuid, user=request.user
    )
    form = WrapUpForm(request.POST or None, instance=session)
    pain_form = PainReportForm(request.POST or None, session=session, prefix="pain")
    if request.method == "POST" and form.is_valid():
        needs_pain = form.cleaned_data.get("had_pain") or session.pain_today
        if needs_pain and not pain_form.is_valid():
            messages.error(request, "Please complete the pain report details.")
        else:
            session = form.save(commit=False)
            session.completed_at = timezone.now()
            completed, prescribed = session_completion(session)
            if prescribed and completed >= prescribed:
                session.status = WorkoutSession.Status.COMPLETED
            elif completed > 0:
                session.status = WorkoutSession.Status.PARTIAL
            else:
                session.status = WorkoutSession.Status.PARTIAL
            session.save()
            if needs_pain:
                pain = pain_form.save(commit=False)
                pain.session = session
                pain.save()
            if session.scheduled_session:
                scheduled = session.scheduled_session
                scheduled.status = (
                    ScheduledSession.Status.COMPLETED
                    if session.status == WorkoutSession.Status.COMPLETED
                    else ScheduledSession.Status.PARTIAL
                )
                scheduled.save(update_fields=["status"])
            prs = detect_prs_for_session(session)
            from coaching.services.progression import generate_recommendations_for_session

            generate_recommendations_for_session(session)
            if prs:
                names = ", ".join(pr.exercise.name for pr in prs[:3])
                messages.success(request, f"Workout complete — new PR on {names}! 🎉")
            else:
                messages.success(request, "Workout complete. Nice work!")
            return redirect("workouts:detail", session_uuid=session.uuid)
    return render(request, "workouts/complete.html", {
        "session": session, "form": form, "pain_form": pain_form,
    })


@login_required
def session_detail(request, session_uuid):
    session = get_object_or_404(
        WorkoutSession.objects.prefetch_related("set_logs__exercise", "pain_reports"),
        uuid=session_uuid, user=request.user,
    )
    logs = session.set_logs.select_related("exercise").order_by("exercise_id", "set_number")
    grouped = {}
    for log in logs:
        grouped.setdefault(log.exercise, []).append(log)
    from progress.models import PersonalRecord

    prs = PersonalRecord.objects.filter(set_log__session=session).select_related("exercise")
    return render(request, "workouts/detail.html", {
        "session": session,
        "grouped": grouped.items(),
        "prs": prs,
        "pain_reports": session.pain_reports.all(),
    })


@login_required
def history(request):
    sessions = WorkoutSession.objects.filter(user=request.user).select_related(
        "workout_day", "program"
    )
    program_id = request.GET.get("program", "")
    exercise_slug = request.GET.get("exercise", "")
    status = request.GET.get("status", "")
    date_from = request.GET.get("from", "")
    date_to = request.GET.get("to", "")
    only_prs = request.GET.get("prs", "")
    only_pain = request.GET.get("pain", "")
    if program_id.isdigit():
        sessions = sessions.filter(program_id=int(program_id))
    if exercise_slug:
        sessions = sessions.filter(set_logs__exercise__slug=exercise_slug).distinct()
    if status in dict(WorkoutSession.Status.choices):
        sessions = sessions.filter(status=status)
    if date_from:
        sessions = sessions.filter(date__gte=date_from)
    if date_to:
        sessions = sessions.filter(date__lte=date_to)
    if only_prs:
        sessions = sessions.filter(set_logs__personal_records__isnull=False).distinct()
    if only_pain:
        sessions = sessions.filter(pain_reports__isnull=False).distinct()
    from programs.models import Program

    return render(request, "workouts/history.html", {
        "sessions": sessions[:100],
        "programs": Program.objects.filter(assigned_to=request.user),
        "exercises": Exercise.objects.filter(
            set_logs__session__user=request.user
        ).distinct().order_by("name"),
        "filters": {
            "program": program_id, "exercise": exercise_slug, "status": status,
            "from": date_from, "to": date_to, "prs": only_prs, "pain": only_pain,
        },
    })


@login_required
def exercise_history_page(request, slug):
    exercise = get_object_or_404(Exercise, slug=slug)
    data = exercise_history(request.user, exercise)
    return render(request, "workouts/exercise_history.html", {
        "exercise": exercise, **data,
    })
