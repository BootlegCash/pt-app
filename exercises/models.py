from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Exercise(models.Model):
    class Muscle(models.TextChoices):
        CHEST = "chest", "Chest"
        BACK = "back", "Back"
        SHOULDERS = "shoulders", "Shoulders"
        BICEPS = "biceps", "Biceps"
        TRICEPS = "triceps", "Triceps"
        FOREARMS = "forearms", "Forearms"
        QUADS = "quads", "Quadriceps"
        HAMSTRINGS = "hamstrings", "Hamstrings"
        GLUTES = "glutes", "Glutes"
        CALVES = "calves", "Calves"
        CORE = "core", "Core"
        LOWER_BACK = "lower_back", "Lower back"
        FULL_BODY = "full_body", "Full body"
        OTHER = "other", "Other"

    class MovementPattern(models.TextChoices):
        HORIZONTAL_PUSH = "horizontal_push", "Horizontal push"
        VERTICAL_PUSH = "vertical_push", "Vertical push"
        HORIZONTAL_PULL = "horizontal_pull", "Horizontal pull"
        VERTICAL_PULL = "vertical_pull", "Vertical pull"
        SQUAT = "squat", "Squat"
        HINGE = "hinge", "Hinge"
        LUNGE = "lunge", "Lunge"
        CARRY = "carry", "Carry"
        ROTATION = "rotation", "Rotation"
        LOCOMOTION = "locomotion", "Locomotion"
        ISOLATION = "isolation_pattern", "Isolation"
        OTHER = "other", "Other"

    class Equipment(models.TextChoices):
        BARBELL = "barbell", "Barbell"
        DUMBBELL = "dumbbell", "Dumbbell"
        KETTLEBELL = "kettlebell", "Kettlebell"
        MACHINE = "machine", "Machine"
        CABLE = "cable", "Cable"
        BODYWEIGHT = "bodyweight", "Bodyweight"
        BAND = "band", "Band"
        SLED = "sled", "Sled"
        LANDMINE = "landmine", "Landmine"
        OTHER = "other", "Other"

    class Category(models.TextChoices):
        STRENGTH = "strength", "Strength"
        HYPERTROPHY = "hypertrophy", "Hypertrophy"
        POWER = "power", "Power"
        PLYOMETRIC = "plyometric", "Plyometric"
        RUNNING = "running", "Running"
        CONDITIONING = "conditioning", "Conditioning"
        MOBILITY = "mobility", "Mobility"
        CORE = "core", "Core"
        REHAB = "rehab", "Rehabilitation"
        WARMUP = "warmup", "Warm-up"

    class Focus(models.TextChoices):
        STRENGTH = "strength", "Strength"
        POWER = "power", "Power"
        HYPERTROPHY = "hypertrophy", "Hypertrophy"
        MIXED = "mixed", "Mixed"

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    primary_muscle = models.CharField(max_length=20, choices=Muscle.choices)
    secondary_muscles = models.JSONField(
        default=list, blank=True, help_text="List of muscle keys, e.g. [\"triceps\"]."
    )
    movement_pattern = models.CharField(
        max_length=20, choices=MovementPattern.choices, default=MovementPattern.OTHER
    )
    equipment = models.CharField(max_length=20, choices=Equipment.choices, default=Equipment.BARBELL)
    exercise_category = models.CharField(max_length=20, choices=Category.choices, default=Category.STRENGTH)
    unilateral = models.BooleanField(default=False)
    is_compound = models.BooleanField(default=True, verbose_name="compound (vs isolation)")
    training_focus = models.CharField(
        max_length=20, choices=Focus.choices, default=Focus.MIXED,
        help_text="Strength / power / hypertrophy classification.",
    )
    instructions = models.TextField(blank=True)
    coaching_cues = models.TextField(blank=True)
    common_mistakes = models.TextField(blank=True)
    substitutions = models.ManyToManyField("self", blank=True, symmetrical=False)
    default_rest_seconds = models.PositiveSmallIntegerField(default=120)
    default_video_url = models.URLField(blank=True)
    public = models.BooleanField(default=True, help_text="Visible to all athletes in the library.")
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="exercises_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)
