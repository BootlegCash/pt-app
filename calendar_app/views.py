from datetime import date as date_cls, datetime
import secrets

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from google_auth_oauthlib.flow import Flow

from core.services.access import get_client_or_404
from workouts.models import WorkoutSession
from workouts.services.history import previous_day_performance

from .models import GoogleCalendarConnection, ScheduledSession
from .services.google_calendar import (
    SCOPES,
    configured as google_calendar_configured,
    delete_session_event,
    encrypt_credentials,
    revoke_connection,
    sync_session,
    sync_upcoming_sessions,
)
from .services.grids import month_grid, week_grid


def _parse_date(raw, fallback):
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return fallback


@login_required
def my_week(request):
    start = _parse_date(request.GET.get("start"), timezone.localdate())
    return render(request, "calendar_app/week.html", {
        "grid": week_grid(request.user, start),
        "athlete": request.user,
        "manage": False,
        "google_calendar_configured": google_calendar_configured(),
        "google_calendar_connected": GoogleCalendarConnection.objects.filter(user=request.user).exists(),
    })


def _google_flow(state=None):
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
                "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_CALENDAR_REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        state=state,
        redirect_uri=settings.GOOGLE_CALENDAR_REDIRECT_URI,
    )


@login_required
def google_connect(request):
    if not google_calendar_configured():
        messages.error(request, "Google Calendar is not configured yet.")
        return redirect("calendar_app:week")
    state = secrets.token_urlsafe(32)
    request.session["google_calendar_oauth_state"] = state
    flow = _google_flow(state)
    url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    return redirect(url)


@login_required
def google_callback(request):
    state = request.session.pop("google_calendar_oauth_state", None)
    if not state or state != request.GET.get("state"):
        messages.error(request, "Google Calendar connection could not be verified. Please try again.")
        return redirect("calendar_app:week")
    try:
        flow = _google_flow(state)
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        GoogleCalendarConnection.objects.update_or_create(
            user=request.user,
            defaults={"encrypted_credentials": encrypt_credentials(flow.credentials)},
        )
        connection = request.user.google_calendar_connection
        sent, failures = sync_upcoming_sessions(connection)
    except Exception:
        messages.error(request, "Google Calendar could not be connected. Please try again.")
        return redirect("calendar_app:week")
    messages.success(
        request,
        f"Google Calendar connected. {sent} upcoming workout{'s' if sent != 1 else ''} synced"
        + (f"; {failures} could not be sent." if failures else "."),
    )
    return redirect("calendar_app:week")


@login_required
@require_POST
def google_disconnect(request):
    connection = GoogleCalendarConnection.objects.filter(user=request.user).first()
    revoked = True
    if connection:
        try:
            revoked = revoke_connection(connection)
        except Exception:
            revoked = False
        connection.delete()
    if revoked:
        messages.success(
            request,
            "Google Calendar disconnected and its access token was revoked. "
            "Existing Google events were left unchanged.",
        )
    else:
        messages.warning(
            request,
            "Google Calendar was disconnected locally, but Google did not confirm token "
            "revocation. Remove PT Portal from your Google Account permissions to finish.",
        )
    return redirect("calendar_app:week")


@login_required
@require_POST
def google_sync(request):
    connection = get_object_or_404(GoogleCalendarConnection, user=request.user)
    sent, failures = sync_upcoming_sessions(connection)
    messages.success(request, f"Synced {sent} upcoming workout{'s' if sent != 1 else ''}." if not failures else f"Synced {sent}; {failures} could not be sent.")
    return redirect("calendar_app:week")


@login_required
def my_month(request):
    today = timezone.localdate()
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
    prescriptions = []
    if session.workout_day:
        from programs.services.prescriptions import resolve_prescribed_weight

        for prescription in session.workout_day.exercises.filter(active=True):
            prescription.resolved = resolve_prescribed_weight(prescription, request.user)
            prescriptions.append(prescription)
    return render(request, "calendar_app/day_detail.html", {
        "session": session,
        "workout_session": workout_session,
        "previous": previous,
        "prescriptions": prescriptions,
    })


# ------------------------------------------------- coach schedule management

class SessionForm(forms.ModelForm):
    class Meta:
        model = ScheduledSession
        fields = ["date", "session_type", "title", "workout_day", "notes"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        from programs.models import WorkoutDayTemplate

        queryset = WorkoutDayTemplate.objects.none()
        if client is not None:
            queryset = WorkoutDayTemplate.objects.filter(
                program_week__program__assigned_to=client
            )
        self.fields["workout_day"].queryset = queryset.select_related(
            "program_week__program"
        )


@login_required
def coach_session_create(request, client_uuid):
    client = get_client_or_404(request.user, client_uuid, manage=True)
    form = SessionForm(request.POST or None, client=client)
    if request.method == "POST" and form.is_valid():
        session = form.save(commit=False)
        session.user = client
        session.program = (
            session.workout_day.program_week.program if session.workout_day else None
        )
        session.save()
        connection = GoogleCalendarConnection.objects.filter(user=client).first()
        if connection:
            try:
                sync_session(connection, session)
            except Exception:
                messages.warning(request, "Session saved, but Google Calendar could not be updated.")
        messages.success(request, "Session added to the client's calendar.")
        return redirect("coaching:client_calendar", client_uuid=client.uuid)
    return render(request, "calendar_app/session_form.html", {
        "form": form, "client": client, "session": None,
    })


@login_required
def coach_session_edit(request, session_uuid):
    session = get_object_or_404(ScheduledSession, uuid=session_uuid)
    client = get_client_or_404(request.user, session.user.uuid, manage=True)
    form = SessionForm(request.POST or None, instance=session, client=client)
    if request.method == "POST" and form.is_valid():
        session = form.save(commit=False)
        session.program = (
            session.workout_day.program_week.program if session.workout_day else None
        )
        session.save()
        connection = GoogleCalendarConnection.objects.filter(user=client).first()
        if connection:
            try:
                sync_session(connection, session)
            except Exception:
                messages.warning(request, "Session saved, but Google Calendar could not be updated.")
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
    connection = GoogleCalendarConnection.objects.filter(user=client).first()
    if connection:
        try:
            delete_session_event(connection, session)
        except Exception:
            messages.warning(request, "Session removed from PT Portal, but its Google Calendar event could not be removed.")
    session.delete()
    messages.success(request, "Session removed from the calendar.")
    return redirect("coaching:client_calendar", client_uuid=client.uuid)
