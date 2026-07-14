from django import forms

from .models import PainReport, WorkoutSession

RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]


class ReadinessForm(forms.ModelForm):
    energy = forms.TypedChoiceField(choices=RATING_CHOICES, coerce=int, widget=forms.RadioSelect)
    sleep_quality = forms.TypedChoiceField(choices=RATING_CHOICES, coerce=int, widget=forms.RadioSelect)
    soreness = forms.TypedChoiceField(choices=RATING_CHOICES, coerce=int, widget=forms.RadioSelect)
    stress = forms.TypedChoiceField(choices=RATING_CHOICES, coerce=int, widget=forms.RadioSelect)
    motivation = forms.TypedChoiceField(choices=RATING_CHOICES, coerce=int, widget=forms.RadioSelect)

    class Meta:
        model = WorkoutSession
        fields = ["energy", "sleep_quality", "soreness", "stress", "motivation", "pain_today"]


class WrapUpForm(forms.ModelForm):
    class Meta:
        model = WorkoutSession
        fields = [
            "session_difficulty", "pump_rating", "performance_rating",
            "had_pain", "notes",
        ]
        widgets = {
            "session_difficulty": forms.NumberInput(attrs={"min": 1, "max": 10}),
            "pump_rating": forms.NumberInput(attrs={"min": 1, "max": 5}),
            "performance_rating": forms.NumberInput(attrs={"min": 1, "max": 5}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class PainReportForm(forms.ModelForm):
    class Meta:
        model = PainReport
        fields = [
            "body_location", "severity", "pain_type", "exercise",
            "affected_performance", "notes",
        ]
        widgets = {
            "severity": forms.NumberInput(attrs={"min": 1, "max": 10}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, session=None, **kwargs):
        super().__init__(*args, **kwargs)
        if session is not None and session.workout_day:
            from exercises.models import Exercise

            self.fields["exercise"].queryset = Exercise.objects.filter(
                prescriptions__workout_day=session.workout_day
            ).distinct()
