from datetime import date

from django import forms
from django.db.models import Q

from accounts.models import User

from .models import Program, ProgramWeek, WorkoutDayTemplate, WorkoutExercise


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = [
            "name", "description", "main_goal", "start_date", "number_of_weeks",
            "progression_enabled", "client_visible_notes", "coach_notes",
        ]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"})}

    def clean_number_of_weeks(self):
        number = self.cleaned_data["number_of_weeks"]
        if self.instance.pk and self.instance.weeks.filter(
            week_number__gt=number, days__isnull=False
        ).exists():
            raise forms.ValidationError(
                "Remove workout days from later weeks before shortening the program."
            )
        return number


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
        help_text=(
            "Optional. Enter working-set weights separated by commas. "
            "Leave a position blank when that set has no assigned weight, e.g. 185, , 205."
        ),
        widget=forms.TextInput(attrs={"placeholder": "185, , 205"}),
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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from exercises.models import Exercise

        exercises = Exercise.objects.filter(active=True)
        if user and (user.is_staff or user.is_superuser):
            # Administrators can manage every active exercise, including
            # coach-private entries.
            pass
        elif user and user.is_authenticated:
            exercises = exercises.filter(Q(public=True) | Q(created_by=user))
        else:
            # A missing actor must never broaden access accidentally.
            exercises = exercises.filter(public=True)
        self.fields["exercise"].queryset = exercises
        if self.instance and self.instance.pk:
            self.fields["set_weight_targets_text"].initial = ", ".join(
                "" if weight is None else str(weight)
                for weight in self.instance.set_weight_targets_lb
            )

    def clean_set_weight_targets_text(self):
        raw = self.cleaned_data.get("set_weight_targets_text", "").strip()
        if not raw:
            return []
        weights = []
        for item in raw.split(","):
            if not item.strip():
                weights.append(None)
                continue
            try:
                weight = float(item.strip())
            except ValueError as error:
                raise forms.ValidationError(
                    "Use numbers separated by commas, such as 290, 305."
                ) from error
            if weight < 0 or weight > 9999:
                raise forms.ValidationError("Each weight must be between 0 and 9,999 lb.")
            weights.append(weight)
        if not any(weight is not None for weight in weights):
            return []
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


class ClientChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, client):
        return f"{client.display_label} ({client.username})"


class AssignProgramToClientForm(forms.Form):
    client = ClientChoiceField(
        queryset=User.objects.none(),
        empty_label="Choose a client",
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), required=True
    )

    def __init__(self, *args, clients, program=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = clients
        self.initial.setdefault(
            "start_date",
            program.start_date if program and program.start_date else date.today(),
        )
        if program and program.assigned_to_id:
            self.initial.setdefault("client", program.assigned_to_id)
