import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.services.storage import get_private_storage, randomized_name


def profile_photo_path(instance, filename):
    return f"profile_photos/{randomized_name(filename)}"


class AthleteProfile(models.Model):
    """Administrator/coach-controlled athlete data. Clients have read access only.

    Weights are stored in pounds and heights in inches; nutrition services
    convert to metric internally.
    """

    class Sex(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"

    class TrainingGoal(models.TextChoices):
        CUT = "cut", "Cut"
        RECOMP = "recomp", "Body recomposition"
        MAINTAIN = "maintain", "Maintain"
        LEAN_BULK = "lean_bulk", "Lean bulk"
        PERFORMANCE = "performance", "Performance"
        STRENGTH = "strength", "Strength"
        HYPERTROPHY = "hypertrophy", "Hypertrophy"
        GENERAL = "general", "General fitness"

    class Experience(models.TextChoices):
        BEGINNER = "beginner", "Beginner (<1 year)"
        NOVICE = "novice", "Novice (1–2 years)"
        INTERMEDIATE = "intermediate", "Intermediate (2–5 years)"
        ADVANCED = "advanced", "Advanced (5+ years)"

    class ActivityLevel(models.TextChoices):
        SEDENTARY = "sedentary", "Sedentary"
        LIGHT = "light", "Lightly active"
        MODERATE = "moderate", "Moderately active"
        VERY = "very", "Very active"
        EXTREME = "extreme", "Extremely active"

    class OccupationActivity(models.TextChoices):
        SEATED = "seated", "Mostly seated"
        MIXED = "mixed", "Mixed sitting/standing"
        STANDING = "standing", "On feet most of the day"
        PHYSICAL = "physical", "Physically demanding"

    class AccountStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="athlete_profile"
    )
    display_name = models.CharField(max_length=100, blank=True)
    profile_photo = models.ImageField(
        upload_to=profile_photo_path, storage=get_private_storage,
        blank=True, null=True,
    )
    birth_date = models.DateField(null=True, blank=True)
    sex_for_calculations = models.CharField(
        max_length=10, choices=Sex.choices, blank=True,
        help_text="Used only for energy-expenditure and body-fat equations.",
    )
    height_inches = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    current_weight_lb = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    goal_weight_lb = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    training_goal = models.CharField(
        max_length=20, choices=TrainingGoal.choices, default=TrainingGoal.GENERAL
    )
    training_experience = models.CharField(
        max_length=20, choices=Experience.choices, default=Experience.BEGINNER
    )
    activity_level = models.CharField(
        max_length=20, choices=ActivityLevel.choices, default=ActivityLevel.LIGHT
    )
    occupation_activity = models.CharField(
        max_length=20, choices=OccupationActivity.choices, default=OccupationActivity.SEATED
    )
    weekly_lifting_days = models.PositiveSmallIntegerField(default=3)
    weekly_running_days = models.PositiveSmallIntegerField(default=0)
    current_program = models.ForeignKey(
        "programs.Program", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="active_athletes",
    )
    program_start_date = models.DateField(null=True, blank=True)
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="coached_profiles",
        limit_choices_to={"is_coach": True},
    )
    account_status = models.CharField(
        max_length=10, choices=AccountStatus.choices, default=AccountStatus.ACTIVE
    )
    general_notes = models.TextField(
        blank=True, help_text="Coach/administrator notes. Not shown to the client."
    )
    movement_limitations = models.TextField(blank=True)
    injury_cautions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile: {self.user.username}"

    @property
    def age(self):
        if not self.birth_date:
            return None
        today = timezone.localdate()
        years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years

    @property
    def name(self):
        return self.display_name or self.user.display_label

    @property
    def height_display(self):
        if self.height_inches is None:
            return ""
        total = float(self.height_inches)
        return f"{int(total // 12)}'{total % 12:.0f}\""


class Measurement(models.Model):
    """Point-in-time body measurements, entered by coach/administrator.

    Circumference values are inches; bodyweight is pounds. Body-fat values are
    rough estimates only — never presented as exact.
    """

    class Method(models.TextChoices):
        TAPE = "tape", "Tape measure"
        NAVY = "navy", "Navy circumference estimate"
        CALIPER = "caliper", "Calipers"
        SCALE = "scale", "Smart scale / BIA"
        DEXA = "dexa", "DEXA scan"
        VISUAL = "visual", "Visual estimate"
        OTHER = "other", "Other"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="measurements"
    )
    date = models.DateField(db_index=True)
    bodyweight_lb = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    neck = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    shoulders = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    chest = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    waist = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    hips = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    left_arm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    right_arm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    left_forearm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    right_forearm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    left_thigh = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    right_thigh = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    left_calf = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    right_calf = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    estimated_body_fat = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text="Rough estimate (%). May be manually overridden by the coach.",
    )
    measurement_method = models.CharField(
        max_length=10, choices=Method.choices, default=Method.TAPE
    )
    notes = models.TextField(blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="measurements_entered",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.user.username} @ {self.date}"

    CIRCUMFERENCE_FIELDS = [
        "neck", "shoulders", "chest", "waist", "hips",
        "left_arm", "right_arm", "left_forearm", "right_forearm",
        "left_thigh", "right_thigh", "left_calf", "right_calf",
    ]
