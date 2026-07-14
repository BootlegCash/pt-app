"""Small, privacy-conscious Google Calendar integration.

Only schedule metadata leaves PT Portal: workout title, date, short notes and
the link back to the athlete's session. Measurements, health flags, coaching
notes, nutrition and logged workout data are never included.
"""

from __future__ import annotations

import json
from datetime import timedelta

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def configured() -> bool:
    return bool(
        settings.GOOGLE_CALENDAR_ENABLED
        and settings.GOOGLE_CALENDAR_CLIENT_ID
        and settings.GOOGLE_CALENDAR_CLIENT_SECRET
        and settings.GOOGLE_CALENDAR_REDIRECT_URI
        and settings.GOOGLE_TOKEN_ENCRYPTION_KEY
    )


def _fernet() -> Fernet:
    if not settings.GOOGLE_TOKEN_ENCRYPTION_KEY:
        raise ImproperlyConfigured("GOOGLE_TOKEN_ENCRYPTION_KEY is required for Google Calendar.")
    return Fernet(settings.GOOGLE_TOKEN_ENCRYPTION_KEY.encode())


def encrypt_credentials(credentials: Credentials) -> str:
    payload = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }
    return _fernet().encrypt(json.dumps(payload).encode()).decode()


def credentials_for(connection) -> Credentials:
    payload = json.loads(_fernet().decrypt(connection.encrypted_credentials.encode()).decode())
    credentials = Credentials.from_authorized_user_info(payload, SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        connection.encrypted_credentials = encrypt_credentials(credentials)
        connection.save(update_fields=["encrypted_credentials", "updated_at"])
    return credentials


def _event_body(session) -> dict:
    day_url = settings.SITE_URL.rstrip("/") + reverse(
        "calendar_app:day_detail", kwargs={"session_uuid": session.uuid}
    )
    description = "Scheduled in PT Portal.\nOpen your workout: " + day_url
    if session.notes:
        description += "\n\nCoach note: " + session.notes[:500]
    return {
        "summary": session.title,
        "description": description,
        "start": {"date": session.date.isoformat()},
        "end": {"date": (session.date + timedelta(days=1)).isoformat()},
        "extendedProperties": {"private": {"pt_portal_session": str(session.uuid)}},
    }


def sync_session(connection, session) -> None:
    """Create or update one all-day workout event in the athlete's calendar."""
    service = build("calendar", "v3", credentials=credentials_for(connection), cache_discovery=False)
    body = _event_body(session)
    if session.google_event_id:
        event = service.events().update(
            calendarId=connection.calendar_id, eventId=session.google_event_id, body=body
        ).execute()
    else:
        event = service.events().insert(calendarId=connection.calendar_id, body=body).execute()
        session.google_event_id = event["id"]
    session.google_synced_at = timezone.now()
    session.save(update_fields=["google_event_id", "google_synced_at"])


def delete_session_event(connection, session) -> None:
    if not session.google_event_id:
        return
    service = build("calendar", "v3", credentials=credentials_for(connection), cache_discovery=False)
    service.events().delete(calendarId=connection.calendar_id, eventId=session.google_event_id).execute()


def sync_upcoming_sessions(connection) -> tuple[int, int]:
    """Sync future sessions, returning (sent, failures) without stopping halfway."""
    from calendar_app.models import ScheduledSession

    sent = failures = 0
    for session in ScheduledSession.objects.filter(user=connection.user, date__gte=timezone.localdate()):
        try:
            sync_session(connection, session)
            sent += 1
        except Exception:
            failures += 1
    return sent, failures
