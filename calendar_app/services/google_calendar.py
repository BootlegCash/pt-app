"""Small, privacy-conscious Google Calendar integration.

Only schedule metadata leaves PT Portal: workout title, date, short notes and
the link back to the athlete's session. Measurements, health flags, coaching
notes, nutrition and logged workout data are never included.
"""

from __future__ import annotations

import json
from datetime import timedelta

import requests
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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
    return {
        "summary": session.title,
        "description": description,
        "start": {"date": session.date.isoformat()},
        "end": {"date": (session.date + timedelta(days=1)).isoformat()},
        "extendedProperties": {"private": {"pt_portal_session": str(session.uuid)}},
    }


def _calendar_service(connection):
    return build(
        "calendar",
        "v3",
        credentials=credentials_for(connection),
        cache_discovery=False,
    )


def sync_session(connection, session, *, service=None) -> None:
    """Create or update one all-day workout event in the athlete's calendar."""
    service = service or _calendar_service(connection)
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


def delete_session_event(connection, session, *, service=None) -> None:
    if not session.google_event_id:
        return
    delete_event_by_id(connection, session.google_event_id, service=service)


def delete_event_by_id(connection, event_id, *, service=None) -> None:
    """Delete a known remote event without requiring its local row to exist."""
    service = service or _calendar_service(connection)
    service.events().delete(calendarId=connection.calendar_id, eventId=event_id).execute()


def revoke_connection(connection) -> bool:
    """Revoke the provider token before removing the local connection."""
    credentials = credentials_for(connection)
    token = credentials.refresh_token or credentials.token
    if not token:
        return True
    response = requests.post(
        "https://oauth2.googleapis.com/revoke",
        data={"token": token},
        headers={"content-type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    return response.status_code in {200, 400}


def _process_pending_deletions(connection, service) -> int:
    """Process durable stale-event deletions, returning the failure count."""
    from calendar_app.models import GoogleCalendarDeletion

    failures = 0
    for deletion in GoogleCalendarDeletion.objects.filter(
        user=connection.user, processed_at__isnull=True
    )[:500]:
        try:
            delete_event_by_id(connection, deletion.event_id, service=service)
        except HttpError as error:
            if getattr(error.resp, "status", None) not in {404, 410}:
                deletion.attempts += 1
                deletion.last_error = str(error)[:1000]
                deletion.save(update_fields=["attempts", "last_error"])
                failures += 1
                continue
        except Exception as error:
            deletion.attempts += 1
            deletion.last_error = str(error)[:1000]
            deletion.save(update_fields=["attempts", "last_error"])
            failures += 1
            continue
        deletion.processed_at = timezone.now()
        deletion.last_error = ""
        deletion.save(update_fields=["processed_at", "last_error"])
    return failures


def sync_upcoming_sessions(connection) -> tuple[int, int]:
    """Sync future sessions, returning (sent, failures) without stopping halfway."""
    from calendar_app.models import ScheduledSession

    service = _calendar_service(connection)
    sent = 0
    failures = _process_pending_deletions(connection, service)
    for session in ScheduledSession.objects.filter(user=connection.user, date__gte=timezone.localdate()):
        try:
            sync_session(connection, session, service=service)
            sent += 1
        except Exception:
            failures += 1
    return sent, failures
