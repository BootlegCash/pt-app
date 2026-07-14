from datetime import date as date_cls, datetime

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.services.access import get_client_or_404
from workouts.models import WorkoutSession
from workouts.services.history import previous_day_performance

from .models import ScheduledSession
from .services.grids import month_grid, week_grid


def _parse_date(raw, fallback):
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return fallback


@login_required
def my_week(request):
    start = _parse_date(request.GET.get("start"), date_cls.today())
    return render(request, "calendar_app/week.html", {
        "grid": week_grid(request.user, start),
        "athlete": request.user,
        "manage": False,
    })


@login_required
def my_month(request):
    today = date_cls.today()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        date_cls(year, month, 1)
    except ValueError:
        year, month = today.year, today.month
    return render(request, "calendar_app/month.html", {
        "grid": month_grid(request.user, year, month),
        "athlete": request.user,
        "manage": False,
    })


@login_required
def day_detail(request, session_uuid):
    session = get_object_or_404(
        ScheduledSession.objects.select_related(
            "workout_day__program_week__program", "program"
        ).prefetch_related("workout_day__exercises__exercise"),
        uuid=session_uuid, user=request.user,
    )
    workout_session = WorkoutSession.objects.filter(
        user=request.user, scheduled_session=session
    ).first()
    previous = (
        previous_day_performance(request.user, session.workout_day)
        if session.workout_day else {}
    )
    return render(request, "calendar_app/day_detail.html", {
        "session": session,
        "workout_session": workout_session,
        "previous": previous,
    })


# ------------------------------------------------- coach schedule management

class SessionForm(forms.ModelForm):
    class Meta:
        model = ScheduledSession
        fields = ["date", "session_type", "title", "workout_day", "notes"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


@login_required
def coach_session_create(request, client_uuid):
    client = get_client_or_404(request.user, client_uuid, manage=True)
    form = SessionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        session = form.save(commit=False)
        session.user = client
        session.save()
        messages.success(request, "Session added to the client's calendar.")
        return redirect("coaching:client_calendar", client_uuid=client.uuid)
    return render(request, "calendar_app/session_form.html", {
        "form": form, "client": client, "session": None,
    })


@login_required
def coach_session_edit(request, session_uuid):
    session = get_object_or_404(ScheduledSession, uuid=session_uuid)
    client = get_client_or_404(request.user, session.user.uuid, manage=True)
    form = SessionForm(request.POST or None, instance=session)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Session updated.")
        return redirect("coaching:client_calendar", client_uuid=client.uuid)
    return render(request, "calendar_app/session_form.html", {
        "form": form, "client": client, "session": session,
    })


@login_required
@require_POST
def coach_session_delete(request, session_uuid):
    session = get_object_or_404(ScheduledSession, uuid=session_uuid)
    client = get_client_or_404(request.user, session.user.uuid, manage=True)
    session.delete()
    messages.success(request, "Session removed from the calendar.")
    return redirect("coaching:client_calendar", client_uuid=client.uuid)
