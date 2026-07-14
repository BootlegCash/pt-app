import uuid

from django.conf import settings
from django.db import models


class CoachClientRelationship(models.Model):
    """Grants a coach access to a client while ACTIVE. Managed by administrators."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        ENDED = "ended", "Ended"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="client_relationships", limit_choices_to={"is_coach": True},
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="coach_relationships",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    private_notes = models.TextField(blank=True, help_text="Never visible to the client.")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["coach", "client"], name="unique_coach_client")
        ]

    def __str__(self):
        return f"{self.coach.username} → {self.client.username} ({self.status})"

    def save(self, *args, **kwargs):
        from django.utils import timezone

        if self.status == self.Status.ACTIVE and self.activated_at is None:
            self.activated_at = timezone.now()
        if self.status == self.Status.ENDED and self.ended_at is None:
            self.ended_at = timezone.now()
        super().save(*args, **kwargs)


class ProgressionRecommendation(models.Model):
    """A suggested next-step for one prescription. Never applied silently —
    a coach approves, modifies, or rejects every recommendation."""

    class Action(models.TextChoices):
        REPEAT = "repeat", "Repeat current weight"
        ADD_WEIGHT = "add_weight", "Increase weight"
        REDUCE_WEIGHT = "reduce_weight", "Reduce weight"
        ADD_REP = "add_rep", "Add one rep per set"
        IMPROVE_RIR = "improve_rir", "Keep load, improve RIR"
        DELOAD = "deload", "Schedule a deload"
        COLLECT_DATA = "collect_data", "Continue collecting data"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        MODIFIED = "modified", "Modified"
        REJECTED = "rejected", "Rejected"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="progression_recommendations",
    )
    workout_exercise = models.ForeignKey(
        "programs.WorkoutExercise", on_delete=models.CASCADE,
        related_name="progression_recommendations",
    )
    source_session = models.ForeignKey(
        "workouts.WorkoutSession", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="progression_recommendations",
    )
    action = models.CharField(max_length=15, choices=Action.choices)
    amount_lb = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    reasoning = models.TextField()
    previous_performance = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="progressions_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} — {self.workout_exercise}"
