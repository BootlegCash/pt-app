import uuid

from django.conf import settings
from django.db import models


class LiftMax(models.Model):
    """A recorded max for one lift (tested, estimated, rep max, or coach-assigned)."""

    class MaxType(models.TextChoices):
        TESTED = "tested", "Tested 1RM"
        ESTIMATED = "estimated", "Estimated 1RM"
        REP_MAX = "rep_max", "Rep max"
        TRAINING = "training", "Training max"
        COACH = "coach", "Coach-assigned max"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lift_maxes"
    )
    exercise = models.ForeignKey(
        "exercises.Exercise", on_delete=models.PROTECT, related_name="lift_maxes"
    )
    max_type = models.CharField(max_length=12, choices=MaxType.choices)
    weight_lb = models.DecimalField(max_digits=6, decimal_places=1)
    reps = models.PositiveSmallIntegerField(
        default=1, help_text="Reps performed at that weight (1 for a true 1RM)."
    )
    estimated_1rm = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    tested_1rm = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    date = models.DateField(db_index=True)
    bodyweight_at_time_lb = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    notes = models.TextField(blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="maxes_entered",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name_plural = "lift maxes"

    def __str__(self):
        return f"{self.user.username}: {self.exercise.name} {self.weight_lb}×{self.reps}"

    def save(self, *args, **kwargs):
        from progress.services.one_rm import default_estimate

        if self.estimated_1rm is None and self.weight_lb and self.reps:
            self.estimated_1rm = round(default_estimate(float(self.weight_lb), self.reps), 1)
        if self.max_type == self.MaxType.TESTED and self.tested_1rm is None and self.reps == 1:
            self.tested_1rm = self.weight_lb
        super().save(*args, **kwargs)

    @property
    def best_value(self):
        return self.tested_1rm or self.estimated_1rm or self.weight_lb

    def bodyweight_ratio(self):
        if self.bodyweight_at_time_lb and self.best_value:
            return round(float(self.best_value) / float(self.bodyweight_at_time_lb), 2)
        return None


class PersonalRecord(models.Model):
    """Automatically detected training PRs (plus tested-max PRs)."""

    class RecordType(models.TextChoices):
        WEIGHT = "weight", "Heaviest weight"
        E1RM = "e1rm", "Best estimated 1RM"
        REPS = "reps", "Most reps at a weight"
        TESTED = "tested", "Tested max"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="personal_records"
    )
    exercise = models.ForeignKey(
        "exercises.Exercise", on_delete=models.PROTECT, related_name="personal_records"
    )
    record_type = models.CharField(max_length=10, choices=RecordType.choices)
    value = models.DecimalField(max_digits=7, decimal_places=1)
    weight_lb = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    reps = models.PositiveSmallIntegerField(null=True, blank=True)
    previous_value = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    date = models.DateField(db_index=True)
    set_log = models.ForeignKey(
        "workouts.SetLog", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="personal_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"PR {self.exercise.name} {self.get_record_type_display()}: {self.value}"
