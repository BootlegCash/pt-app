from django import forms
from django.contrib.auth.password_validation import validate_password

from accounts.models import User
from progress.models import LiftMax


class CreateUserForm(forms.Form):
    """Administrator-only account creation (public registration is disabled)."""

    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    is_coach = forms.BooleanField(required=False)
    is_athlete = forms.BooleanField(required=False, initial=True)
    temporary_password = forms.CharField(
        required=False,
        help_text="Leave blank to generate one automatically.",
    )
    active = forms.BooleanField(required=False, initial=True)
    coach = forms.ModelChoiceField(
        queryset=User.objects.filter(is_coach=True, is_active=True), required=False
    )

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("That email is already in use.")
        return email

    def clean_temporary_password(self):
        password = self.cleaned_data.get("temporary_password", "")
        if password:
            validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("is_coach") and not cleaned.get("is_athlete"):
            raise forms.ValidationError("Select at least one role.")
        return cleaned


class LiftMaxForm(forms.ModelForm):
    class Meta:
        model = LiftMax
        fields = [
            "exercise", "max_type", "weight_lb", "reps",
            "tested_1rm", "date", "bodyweight_at_time_lb", "notes",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class PrivateNotesForm(forms.Form):
    private_notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6}), required=False,
        label="Private coach notes (never visible to the client)",
    )


class ReviewForm(forms.Form):
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    modified_amount = forms.DecimalField(
        required=False, max_digits=5, decimal_places=1, min_value=0.1,
        help_text="Override the recommended weight change (lb).",
    )
