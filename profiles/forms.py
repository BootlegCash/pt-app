from django import forms

from .models import AthleteProfile, Measurement


class AthleteProfileForm(forms.ModelForm):
    """Used only by administrators/coaches — clients never edit profiles."""

    class Meta:
        model = AthleteProfile
        fields = [
            "display_name", "profile_photo", "birth_date", "sex_for_calculations",
            "height_inches", "current_weight_lb", "goal_weight_lb",
            "training_goal", "training_experience", "activity_level",
            "occupation_activity", "weekly_lifting_days", "weekly_running_days",
            "coach", "account_status", "general_notes",
            "movement_limitations", "injury_cautions",
        ]
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"})}

    def clean_profile_photo(self):
        from imports.services.validation import validate_image_upload

        photo = self.cleaned_data.get("profile_photo")
        if photo and hasattr(photo, "content_type"):
            validate_image_upload(photo)
        return photo


class MeasurementForm(forms.ModelForm):
    class Meta:
        model = Measurement
        fields = [
            "date", "bodyweight_lb", "neck", "shoulders", "chest", "waist", "hips",
            "left_arm", "right_arm", "left_forearm", "right_forearm",
            "left_thigh", "right_thigh", "left_calf", "right_calf",
            "estimated_body_fat", "measurement_method", "notes",
        ]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}
