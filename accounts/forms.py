from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username or email",
        widget=forms.TextInput(
            attrs={"autofocus": True, "autocomplete": "username", "class": "input"}
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "class": "input"}
        ),
    )


class ForcedPasswordChangeForm(SetPasswordForm):
    """First-login password change; clears the must_change_password flag."""

    def save(self, commit=True):
        user = super().save(commit=False)
        user.must_change_password = False
        if commit:
            user.save()
        return user
