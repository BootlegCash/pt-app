import uuid

from django.conf import settings
from django.db import models


class MacroRuleSet(models.Model):
    """Configurable macro rules. The calculator reads the active ruleset instead
    of hardcoding coefficients, so coaching philosophy can change without code."""

    name = models.CharField(max_length=100, default="Default rules")
    active = models.BooleanField(default=True)

    protein_g_per_lb = models.DecimalField(max_digits=4, decimal_places=2, default=0.8)
    protein_g_per_lb_cut = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.0,
        help_text="Higher protein while cutting / recomping.",
    )
    fat_percent_calories = models.DecimalField(max_digits=4, decimal_places=1, default=25)
    fat_minimum_g_per_lb = models.DecimalField(max_digits=4, decimal_places=2, default=0.25)
    fiber_g_per_1000_kcal = models.DecimalField(max_digits=4, decimal_places=1, default=14)
    water_oz_per_lb = models.DecimalField(max_digits=4, decimal_places=2, default=0.5)

    cut_max_weekly_loss_percent = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.0,
        help_text="Weekly loss above this % of bodyweight is flagged.",
    )
    recomp_deficit_percent = models.DecimalField(max_digits=4, decimal_places=1, default=5)
    performance_surplus_kcal = models.PositiveSmallIntegerField(default=150)
    kcal_per_lb_weekly_change = models.PositiveSmallIntegerField(
        default=500, help_text="Daily kcal delta per 1 lb/week of weight change.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @classmethod
    def get_active(cls):
        ruleset = cls.objects.filter(active=True).order_by("-updated_at").first()
        return ruleset or cls.objects.create(name="Default rules")


class NutritionTarget(models.Model):
    """Current assigned nutrition targets. Both the raw calculation and the
    coach's final (possibly overridden) numbers are stored and displayed."""

    class Method(models.TextChoices):
        MIFFLIN = "mifflin", "Mifflin-St Jeor"
        KATCH = "katch", "Katch-McArdle"
        MANUAL = "manual", "Manual"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="nutrition_target"
    )
    goal = models.CharField(max_length=20, blank=True)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.MIFFLIN)

    maintenance_calories = models.PositiveIntegerField(null=True, blank=True)
    expected_weekly_change_lb = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        help_text="Negative = loss, positive = gain.",
    )

    calculated_calories = models.PositiveIntegerField(null=True, blank=True)
    calculated_protein_g = models.PositiveIntegerField(null=True, blank=True)
    calculated_carbs_g = models.PositiveIntegerField(null=True, blank=True)
    calculated_fat_g = models.PositiveIntegerField(null=True, blank=True)
    calculated_fiber_g = models.PositiveIntegerField(null=True, blank=True)
    calculated_water_oz = models.PositiveIntegerField(null=True, blank=True)

    final_calories = models.PositiveIntegerField(null=True, blank=True)
    final_protein_g = models.PositiveIntegerField(null=True, blank=True)
    final_carbs_g = models.PositiveIntegerField(null=True, blank=True)
    final_fat_g = models.PositiveIntegerField(null=True, blank=True)
    final_fiber_g = models.PositiveIntegerField(null=True, blank=True)
    final_water_oz = models.PositiveIntegerField(null=True, blank=True)

    sodium_guidance = models.CharField(max_length=300, blank=True)
    pre_workout_suggestion = models.TextField(blank=True)
    post_workout_suggestion = models.TextField(blank=True)
    example_meals = models.TextField(blank=True)
    coach_notes = models.TextField(blank=True)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="nutrition_targets_updated",
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nutrition targets: {self.user.username}"

    def macro(self, name):
        """Final value with calculated fallback, e.g. target.macro('calories')."""
        final = getattr(self, f"final_{name}")
        return final if final is not None else getattr(self, f"calculated_{name}")

    # Template-friendly accessors (final value, calculated fallback)
    @property
    def macro_calories(self):
        return self.macro("calories")

    @property
    def macro_protein(self):
        return self.macro("protein_g")

    @property
    def macro_carbs(self):
        return self.macro("carbs_g")

    @property
    def macro_fat(self):
        return self.macro("fat_g")

    @property
    def macro_fiber(self):
        return self.macro("fiber_g")

    @property
    def macro_water(self):
        return self.macro("water_oz")

    @property
    def has_targets(self):
        return self.macro_calories is not None


class NutritionCheckin(models.Model):
    """Optional daily yes/no target check-ins (no food logging required)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="nutrition_checkins"
    )
    date = models.DateField()
    calories_met = models.BooleanField(default=False)
    protein_met = models.BooleanField(default=False)
    water_met = models.BooleanField(default=False)
    fiber_met = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="unique_checkin_per_day")
        ]

    def __str__(self):
        return f"{self.user.username} check-in {self.date}"
