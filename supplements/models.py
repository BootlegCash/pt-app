import uuid

from django.conf import settings
from django.db import models

EDUCATIONAL_DISCLAIMER = (
    "Educational information only — not medical advice, and not a treatment "
    "for any disease. Talk with a qualified healthcare professional before "
    "starting any supplement, especially if you take medication or have a "
    "medical condition."
)


class Supplement(models.Model):
    """Library entry describing one supplement in conservative, educational terms."""

    class Category(models.TextChoices):
        PERFORMANCE = "performance", "Performance"
        RECOVERY = "recovery", "Recovery"
        GENERAL_HEALTH = "general_health", "General health"
        PROTEIN = "protein", "Protein"
        HYDRATION = "hydration", "Hydration"
        VITAMIN_MINERAL = "vitamin_mineral", "Vitamin / mineral"
        OTHER = "other", "Other"

    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    purpose = models.TextField()
    evidence_summary = models.TextField(blank=True)
    default_dose = models.CharField(max_length=100, blank=True)
    dose_unit = models.CharField(max_length=30, blank=True)
    timing = models.CharField(max_length=200, blank=True)
    frequency = models.CharField(max_length=100, blank=True)
    bodyweight_based = models.BooleanField(
        default=False, help_text="Dose commonly scaled to bodyweight (e.g. caffeine)."
    )
    maximum_recommended_amount = models.CharField(max_length=200, blank=True)
    warnings = models.TextField(blank=True)
    interactions = models.TextField(blank=True)
    contraindications = models.TextField(blank=True)
    educational_disclaimer = models.TextField(default=EDUCATIONAL_DISCLAIMER)
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="supplements_created",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserSupplementRecommendation(models.Model):
    """A coach-assigned supplement recommendation for one athlete."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="supplement_recommendations",
    )
    supplement = models.ForeignKey(
        Supplement, on_delete=models.PROTECT, related_name="recommendations"
    )
    assigned_dose = models.CharField(max_length=100)
    dose_unit = models.CharField(max_length=30, blank=True)
    timing = models.CharField(max_length=200, blank=True)
    frequency = models.CharField(max_length=100, blank=True)
    reason = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    coach_notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="supplement_recommendations_entered",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-active", "supplement__name"]

    def __str__(self):
        return f"{self.user.username}: {self.supplement.name}"
