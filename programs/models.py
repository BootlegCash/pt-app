import uuid

from django.conf import settings
from django.db import models


class ProgressionMethod(models.TextChoices):
    """How next-session loads are progressed for a prescribed exercise."""

    DOUBLE = "double", "Double progression (reps then weight)"
    FIXED_LOAD = "fixed_load", "Fixed load increase after success"
    PERCENTAGE = "percentage", "Percentage of training max"
    REP = "rep", "Rep progression at constant weight"
    RIR_RPE = "rir_rpe", "RIR/RPE-gated weight increase"
    MANUAL = "manual", "Manual (coach decides)"
    PERFORMANCE = "performance", "Performance-based recommendation"


class Program(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    class Goal(models.TextChoices):
        STRENGTH = "strength", "Strength"
        HYPERTROPHY = "hypertrophy", "Hypertrophy"
        POWER = "power", "Power"
        FAT_LOSS = "fat_loss", "Fat loss"
        CONDITIONING = "conditioning", "Conditioning"
        GENERAL = "general", "General fitness"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="programs_owned", help_text="Coach/administrator who built it.",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="programs_assigned",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    main_goal = models.CharField(max_length=20, choices=Goal.choices, default=Goal.GENERAL)
    start_date = models.DateField(null=True, blank=True)
    planned_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    number_of_weeks = models.PositiveSmallIntegerField(default=4)
    progression_enabled = models.BooleanField(default=True)
    coach_notes = models.TextField(blank=True, help_text="Never shown to the client.")
    client_visible_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name

    def current_week_number(self, on_date=None):
        from datetime import date as date_cls

        start = self.start_date
        if not start:
            return None
        today = on_date or date_cls.today()
        if today < start:
            return None
        week = (today - start).days // 7 + 1
        return min(week, self.number_of_weeks) if self.number_of_weeks else week

    def assign_to(self, athlete, assigned_by=None, start_date=None):
        """Assign this program to an athlete: profile pointer, status, calendar."""
        from datetime import date as date_cls

        from calendar_app.services.generation import generate_program_schedule
        from core.services.audit import record_change
        from profiles.models import AthleteProfile

        start = start_date or self.start_date or date_cls.today()
        previous = self.assigned_to
        self.assigned_to = athlete
        self.start_date = start
        self.status = self.Status.ACTIVE
        self.save()
        profile, _ = AthleteProfile.objects.get_or_create(user=athlete)
        profile.current_program = self
        profile.program_start_date = start
        profile.save(update_fields=["current_program", "program_start_date", "updated_at"])
        generate_program_schedule(self, athlete)
        record_change(
            changed_by=assigned_by, affected_user=athlete, obj=self,
            field="assigned_to",
            previous=getattr(previous, "username", ""), new=athlete.username,
            reason="Program assignment",
        )
        return self


class ProgramWeek(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="weeks")
    week_number = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=120, blank=True)
    focus = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    deload = models.BooleanField(default=False)
    testing_week = models.BooleanField(default=False)

    class Meta:
        ordering = ["week_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["program", "week_number"], name="unique_week_per_program"
            )
        ]

    def __str__(self):
        return f"{self.program.name} — week {self.week_number}"


class WorkoutDayTemplate(models.Model):
    program_week = models.ForeignKey(
        ProgramWeek, on_delete=models.CASCADE, related_name="days"
    )
    day_number = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=120)
    focus = models.CharField(max_length=120, blank=True)
    default_weekday = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="0=Monday … 6=Sunday. Used when generating the calendar.",
    )
    estimated_duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    warmup_notes = models.TextField(blank=True)
    workout_notes = models.TextField(blank=True)
    cooldown_notes = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "day_number"]

    def __str__(self):
        return f"{self.name} (wk {self.program_week.week_number})"

    WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    @property
    def weekday_name(self):
        if self.default_weekday is None or self.default_weekday > 6:
            return ""
        return self.WEEKDAY_NAMES[self.default_weekday]


class WorkoutExercise(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    workout_day = models.ForeignKey(
        WorkoutDayTemplate, on_delete=models.CASCADE, related_name="exercises"
    )
    exercise = models.ForeignKey(
        "exercises.Exercise", on_delete=models.PROTECT, related_name="prescriptions"
    )
    order = models.PositiveSmallIntegerField(default=0)
    superset_group = models.CharField(
        max_length=5, blank=True, help_text="Exercises sharing a letter are a superset."
    )
    warmup_sets = models.PositiveSmallIntegerField(default=0)
    target_sets = models.PositiveSmallIntegerField(default=3)
    target_rep_min = models.PositiveSmallIntegerField(null=True, blank=True)
    target_rep_max = models.PositiveSmallIntegerField(null=True, blank=True)
    target_reps_text = models.CharField(
        max_length=40, blank=True,
        help_text="Free-form target, e.g. AMRAP, 30 seconds, 20-40 yd.",
    )
    target_weight_lb = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    target_percentage = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text="Percent of training max.",
    )
    target_rir = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    target_rpe = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    tempo = models.CharField(max_length=20, blank=True)
    rest_seconds = models.PositiveSmallIntegerField(null=True, blank=True)
    progression_method = models.CharField(
        max_length=20, choices=ProgressionMethod.choices, default=ProgressionMethod.DOUBLE
    )
    weight_increment_lb = models.DecimalField(
        max_digits=5, decimal_places=1, default=5,
        help_text="Increment used by progression recommendations.",
    )
    client_visible_notes = models.TextField(blank=True)
    private_coach_notes = models.TextField(blank=True)
    optional = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.exercise.name} — {self.workout_day.name}"

    @property
    def rep_target_display(self):
        if self.target_reps_text:
            return self.target_reps_text
        if self.target_rep_min and self.target_rep_max:
            if self.target_rep_min == self.target_rep_max:
                return str(self.target_rep_min)
            return f"{self.target_rep_min}–{self.target_rep_max}"
        if self.target_rep_max:
            return str(self.target_rep_max)
        if self.target_rep_min:
            return f"{self.target_rep_min}+"
        return "—"

    @property
    def effort_display(self):
        if self.target_rir is not None:
            return f"RIR {self.target_rir:g}"
        if self.target_rpe is not None:
            return f"RPE {self.target_rpe:g}"
        return ""
