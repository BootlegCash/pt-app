from django import forms

from profiles.models import AthleteProfile

from .models import NutritionTarget


class CalculatorForm(forms.Form):
    """Coach-facing calculator inputs, prefilled from the athlete profile."""

    sex = forms.ChoiceField(choices=AthleteProfile.Sex.choices)
    age = forms.IntegerField(min_value=13, max_value=100)
    height_inches = forms.DecimalField(min_value=36, max_value=96, decimal_places=1)
    weight_lb = forms.DecimalField(min_value=60, max_value=700, decimal_places=1)
    activity_level = forms.ChoiceField(choices=AthleteProfile.ActivityLevel.choices)
    occupation_activity = forms.ChoiceField(choices=AthleteProfile.OccupationActivity.choices)
    weekly_lifting_days = forms.IntegerField(min_value=0, max_value=7, initial=3)
    weekly_cardio_days = forms.IntegerField(min_value=0, max_value=7, initial=0)
    goal = forms.ChoiceField(choices=[
        ("cut", "Cut"), ("recomp", "Body recomposition"), ("maintain", "Maintain"),
        ("lean_bulk", "Lean bulk"), ("performance", "Performance"),
    ])
    rate_lb_per_week = forms.DecimalField(
        required=False, min_value=0, max_value=3, decimal_places=2,
        help_text="Desired weekly change (lb) for cut / lean bulk.",
    )
    body_fat_percent = forms.DecimalField(
        required=False, min_value=3, max_value=60, decimal_places=1,
        help_text="Optional rough estimate; enables Katch-McArdle.",
    )
    use_katch = forms.BooleanField(
        required=False, label="Use Katch-McArdle (needs body-fat estimate)"
    )
    calorie_adjustment = forms.IntegerField(
        required=False, initial=0, min_value=-1000, max_value=1000,
        help_text="Optional manual kcal adjustment applied to the result.",
    )


class TargetOverrideForm(forms.ModelForm):
    """Coach-assigned final targets and guidance (manual overrides)."""

    class Meta:
        model = NutritionTarget
        fields = [
            "final_calories", "final_protein_g", "final_carbs_g", "final_fat_g",
            "final_fiber_g", "final_water_oz", "sodium_guidance",
            "pre_workout_suggestion", "post_workout_suggestion",
            "example_meals", "coach_notes",
        ]
        widgets = {
            "pre_workout_suggestion": forms.Textarea(attrs={"rows": 2}),
            "post_workout_suggestion": forms.Textarea(attrs={"rows": 2}),
            "example_meals": forms.Textarea(attrs={"rows": 4}),
            "coach_notes": forms.Textarea(attrs={"rows": 3}),
        }


class CheckinForm(forms.Form):
    calories_met = forms.BooleanField(required=False)
    protein_met = forms.BooleanField(required=False)
    water_met = forms.BooleanField(required=False)
    fiber_met = forms.BooleanField(required=False)
