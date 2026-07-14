from django import forms

from .models import Program, ProgramWeek, WorkoutDayTemplate, WorkoutExercise


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = [
            "name", "description", "main_goal", "number_of_weeks",
            "progression_enabled", "client_visible_notes", "coach_notes",
        ]


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


class AssignProgramForm(forms.Form):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), required=True
    )
