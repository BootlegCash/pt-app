import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

RATING_1_5 = [MinValueValidator(1), MaxValueValidator(5)]
RATING_1_10 = [MinValueValidator(1), MaxValueValidator(10)]


class WorkoutSession(models.Model):
    """One executed (or in-progress) workout, logged by the athlete."""

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        PARTIAL = "partial", "Partially completed"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workout_sessions"
    )
    scheduled_session = models.ForeignKey(
        "calendar_app.ScheduledSession", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="workout_sessions",
    )
    workout_day = models.ForeignKey(
        "programs.WorkoutDayTemplate", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sessions",
    )
    program = models.ForeignKey(
        "programs.Program", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sessions",
    )
    date = models.DateField(db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_PROGRESS)

    # Pre-workout readiness (1–5)
    energy = models.PositiveSmallIntegerField(null=True, blank=True, validators=RATING_1_5)
    sleep_quality = models.PositiveSmallIntegerField(null=True, blank=True, validators=RATING_1_5)
    soreness = models.PositiveSmallIntegerField(null=True, blank=True, validators=RATING_1_5)
    stress = models.PositiveSmallIntegerField(null=True, blank=True, validators=RATING_1_5)
    motivation = models.PositiveSmallIntegerField(null=True, blank=True, validators=RATING_1_5)
    pain_today = models.BooleanField(default=False)

    # Post-workout feedback
    session_difficulty = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=RATING_1_10, help_text="1 easy – 10 maximal"
    )
    pump_rating = models.PositiveSmallIntegerField(null=True, blank=True, validators=RATING_1_5)
    performance_rating = models.PositiveSmallIntegerField(null=True, blank=True, validators=RATING_1_5)
    had_pain = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-started_at"]

    def __str__(self):
        return f"{self.user.username} — {self.title} @ {self.date}"

    @property
    def title(self):
        if self.workout_day:
            return self.workout_day.name
        if self.scheduled_session:
            return self.scheduled_session.title
        return "Workout"

    @property
    def duration_minutes(self):
        if self.completed_at and self.started_at:
            return int((self.completed_at - self.started_at).total_seconds() // 60)
        return None

    @property
    def readiness_average(self):
        values = [
            v for v in (
                self.energy, self.sleep_quality, self.soreness,
                self.stress, self.motivation,
            ) if v is not None
        ]
        if not values:
            return None
        return round(sum(values) / len(values), 1)


class SetLog(models.Model):
    """One performed set. The prescription itself is never mutated by clients."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    session = models.ForeignKey(
        WorkoutSession, on_delete=models.CASCADE, related_name="set_logs"
    )
    workout_exercise = models.ForeignKey(
        "programs.WorkoutExercise", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="set_logs",
    )
    exercise = models.ForeignKey(
        "exercises.Exercise", on_delete=models.PROTECT, related_name="set_logs"
    )
    set_number = models.PositiveSmallIntegerField()
    is_warmup = models.BooleanField(default=False)
    is_extra = models.BooleanField(default=False, help_text="Added beyond the prescription.")
    weight_lb = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    reps = models.PositiveSmallIntegerField(null=True, blank=True)
    rir = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    rpe = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    distance_yards = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    failed = models.BooleanField(default=False)
    substitution_request = models.CharField(
        max_length=200, blank=True,
        help_text="Client may request a substitution; the coach decides.",
    )
    notes = models.CharField(max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["exercise_id", "set_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "workout_exercise", "exercise", "set_number"],
                name="unique_set_per_exercise_per_session",
            )
        ]

    def __str__(self):
        return f"{self.exercise.name} set {self.set_number}"

    @property
    def estimated_1rm(self):
        from progress.services.one_rm import default_estimate

        if self.weight_lb and self.reps:
            return default_estimate(float(self.weight_lb), self.reps)
        return None


class PainReport(models.Model):
    """Client-reported pain. Flagged to the coach; never a diagnosis."""

    class PainType(models.TextChoices):
        SHARP = "sharp", "Sharp"
        ACHING = "aching", "Aching"
        BURNING = "burning", "Burning"
        NUMBNESS = "numbness", "Numbness"
        TINGLING = "tingling", "Tingling"
        WEAKNESS = "weakness", "Weakness"
        INSTABILITY = "instability", "Instability"
        OTHER = "other", "Other"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    session = models.ForeignKey(
        WorkoutSession, on_delete=models.CASCADE, related_name="pain_reports"
    )
    body_location = models.CharField(max_length=100)
    severity = models.PositiveSmallIntegerField(validators=RATING_1_10)
    pain_type = models.CharField(max_length=15, choices=PainType.choices, default=PainType.ACHING)
    exercise = models.ForeignKey(
        "exercises.Exercise", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pain_reports",
    )
    affected_performance = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    reviewed_by_coach = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pain: {self.body_location} ({self.severity}/10)"
