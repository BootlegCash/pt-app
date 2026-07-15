from django import forms

from .models import Program, ProgramWeek, WorkoutDayTemplate, WorkoutExercise


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = [
            "name", "description", "main_goal", "start_date", "number_of_weeks",
            "progression_enabled", "client_visible_notes", "coach_notes",
        ]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"})}


class ProgramWeekForm(forms.ModelForm):
    class Meta:
        model = ProgramWeek
        fields = ["week_number", "title", "focus", "notes", "deload", "testing_week"]


class WorkoutDayForm(forms.ModelForm):
    class Meta:
        model = WorkoutDayTemplate
        fields = [
            "day_number", "name", "focus", "default_weekday",
            "estimated_duration_minutes", "warmup_notes", "workout_notes",
            "cooldown_notes", "order",
        ]


class WorkoutExerciseForm(forms.ModelForm):
    set_weight_targets_text = forms.CharField(
        required=False,
        label="Per-set weights (lb)",
        help_text="Optional. Enter working-set weights separated by commas, e.g. 290, 305.",
        widget=forms.TextInput(attrs={"placeholder": "290, 305"}),
    )

    class Meta:
        model = WorkoutExercise
        fields = [
            "exercise", "order", "superset_group", "warmup_sets", "target_sets",
            "target_rep_min", "target_rep_max", "target_reps_text",
            "target_weight_lb", "target_percentage", "target_rir", "target_rpe",
            "tempo", "rest_seconds", "progression_method", "weight_increment_lb",
            "client_visible_notes", "private_coach_notes", "optional", "active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from exercises.models import Exercise

        self.fields["exercise"].queryset = Exercise.objects.filter(active=True)
        if self.instance and self.instance.pk:
            self.fields["set_weight_targets_text"].initial = ", ".join(
                str(weight) for weight in self.instance.set_weight_targets_lb
            )

    def clean_set_weight_targets_text(self):
        raw = self.cleaned_data.get("set_weight_targets_text", "").strip()
        if not raw:
            return []
        weights = []
        for item in raw.split(","):
            try:
                weight = float(item.strip())
            except ValueError as error:
                raise forms.ValidationError(
                    "Use numbers separated by commas, such as 290, 305."
                ) from error
            if weight < 0 or weight > 9999:
                raise forms.ValidationError("Each weight must be between 0 and 9,999 lb.")
            weights.append(weight)
        if len(weights) > 30:
            raise forms.ValidationError("Enter no more than 30 set weights.")
        return weights

    def save(self, commit=True):
        prescription = super().save(commit=False)
        prescription.set_weight_targets_lb = self.cleaned_data.get(
            "set_weight_targets_text", []
        )
        if commit:
            prescription.save()
            self.save_m2m()
        return prescription


class AssignProgramForm(forms.Form):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), required=True
    )
