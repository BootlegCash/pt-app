import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class GoogleCalendarConnection(models.Model):
    """Encrypted OAuth credentials for one athlete's Google Calendar."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="google_calendar_connection"
    )
    encrypted_credentials = models.TextField()
    calendar_id = models.CharField(max_length=255, default="primary")
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Google Calendar for {self.user.username}"


class GoogleCalendarDeletion(models.Model):
    """Persistent deletion work processed on the athlete's next manual sync."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="google_calendar_deletions",
    )
    event_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event_id"], name="unique_google_deletion_per_user"
            )
        ]


class ScheduledSession(models.Model):
    """One planned session on an athlete's calendar.

    Generated from program weeks on assignment; coaches may add, move, or
    remove sessions manually. Clients cannot modify their schedule.
    """

    class SessionType(models.TextChoices):
        LIFTING = "lifting", "Lifting"
        RUNNING = "running", "Running"
        MOBILITY = "mobility", "Mobility"
        REST = "rest", "Rest day"
        TESTING = "testing", "Testing / max day"
        MEASUREMENT = "measurement", "Measurement"
        CHECKIN = "checkin", "Check-in"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        PARTIAL = "partial", "Partially completed"
        MISSED = "missed", "Missed"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scheduled_sessions"
    )
    date = models.DateField(db_index=True)
    session_type = models.CharField(
        max_length=15, choices=SessionType.choices, default=SessionType.LIFTING
    )
    title = models.CharField(max_length=140)
    program = models.ForeignKey(
        "programs.Program", null=True, blank=True,
        on_delete=models.CASCADE, related_name="scheduled_sessions",
    )
    workout_day = models.ForeignKey(
        "programs.WorkoutDayTemplate", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="scheduled_sessions",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)
    order = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    google_event_id = models.CharField(max_length=255, blank=True)
    google_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "order"]

    def __str__(self):
        return f"{self.title} — {self.user.username} @ {self.date}"

    @property
    def effective_status(self):
        """Missed is derived: a scheduled trainable session whose date passed."""
        if self.status == self.Status.SCHEDULED and self.date < timezone.localdate():
            if self.session_type in {
                self.SessionType.LIFTING, self.SessionType.RUNNING,
                self.SessionType.MOBILITY, self.SessionType.TESTING,
            }:
                return self.Status.MISSED
        return self.status

    @property
    def color_class(self):
        """CSS modifier for calendar cells (see static/css/app.css)."""
        if self.session_type == self.SessionType.TESTING:
            return "cal-testing"
        status = self.effective_status
        if status == self.Status.COMPLETED:
            return "cal-completed"
        if status == self.Status.PARTIAL:
            return "cal-partial"
        if status == self.Status.MISSED:
            return "cal-missed"
        if self.date == timezone.localdate():
            return "cal-today"
        return "cal-upcoming"
