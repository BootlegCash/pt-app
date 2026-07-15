from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import logout, update_session_auth_hash, views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.services import export as export_service
from core.services.audit import record_change

from .forms import ForcedPasswordChangeForm, LoginForm
from .models import LoginAttempt


def _client_ip(request):
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _login_blocked(request, username):
    window_start = timezone.now() - timezone.timedelta(
        minutes=settings.LOGIN_RATE_LIMIT_WINDOW_MINUTES
    )
    LoginAttempt.objects.filter(created_at__lt=window_start).delete()
    ip_address = _client_ip(request)
    recent = LoginAttempt.objects.filter(created_at__gte=window_start)
    identifier_attempts = recent.filter(
        username__iexact=username, ip_address=ip_address
    ).count()
    ip_attempts = recent.filter(ip_address=ip_address).count()
    distributed_identifier_attempts = recent.filter(
        username__iexact=username
    ).count()
    return (
        identifier_attempts >= settings.LOGIN_RATE_LIMIT_ATTEMPTS
        or ip_attempts >= settings.LOGIN_RATE_LIMIT_ATTEMPTS
        or distributed_identifier_attempts >= settings.LOGIN_RATE_LIMIT_ATTEMPTS * 3
    )


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        LoginAttempt.objects.filter(
            ip_address=_client_ip(self.request),
            username__iexact=self.request.POST.get("username", "")[:254],
        ).delete()
        return super().form_valid(form)

    def form_invalid(self, form):
        username = self.request.POST.get("username", "")[:254]
        if username:
            LoginAttempt.objects.create(
                username=username, ip_address=_client_ip(self.request)
            )
            if _login_blocked(self.request, username):
                form.errors.clear()
                form.add_error(
                    None,
                    "Too many failed attempts. Please wait a few minutes and try again.",
                )
        return super().form_invalid(form)

    def post(self, request, *args, **kwargs):
        username = request.POST.get("username", "")[:254]
        if username and _login_blocked(request, username):
            form = self.get_form()
            form.add_error(
                None,
                "Too many failed attempts. Please wait a few minutes and try again.",
            )
            return self.form_invalid_direct(form)
        return super().post(request, *args, **kwargs)

    def form_invalid_direct(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class AdminLoginView(LoginView):
    """Admin-compatible sign-in with the portal's failure throttling."""

    template_name = "admin/login.html"
    authentication_form = AdminAuthenticationForm
    redirect_authenticated_user = False

    def get_success_url(self):
        return self.get_redirect_url() or reverse("admin:index")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(admin.site.each_context(self.request))
        context["app_path"] = self.request.get_full_path()
        return context


@login_required
def force_password_change(request):
    if not request.user.must_change_password:
        return redirect("core:dashboard")
    if request.method == "POST":
        form = ForcedPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password updated. Welcome!")
            return redirect("core:dashboard")
    else:
        form = ForcedPasswordChangeForm(request.user)
    return render(request, "accounts/force_password_change.html", {"form": form})


@login_required
def account_settings(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed.")
            return redirect("accounts:settings")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "accounts/settings.html", {"form": form})


@login_required
def export_data(request):
    """Download every record belonging to the signed-in user as JSON."""
    payload = export_service.export_user_data(request.user)
    response = JsonResponse(payload, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = (
        f'attachment; filename="{request.user.username}-data-export.json"'
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_POST
def deactivate_account(request):
    """Self-service deactivation. Requires current password. Data is retained;
    an administrator can reactivate or permanently delete the account."""
    password = request.POST.get("password", "")
    if not request.user.check_password(password):
        messages.error(request, "Password incorrect — account was not deactivated.")
        return redirect("accounts:settings")
    user = request.user
    record_change(
        changed_by=user, affected_user=user, obj=user,
        field="is_active", previous=True, new=False,
        reason="Self-service account deactivation",
    )
    user.is_active = False
    user.save(update_fields=["is_active"])
    logout(request)
    messages.info(
        request,
        "Your account has been deactivated. Contact your administrator to "
        "reactivate it or to request permanent deletion of your data.",
    )
    return redirect("accounts:login")


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = "/accounts/password-reset/done/"


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = "/accounts/password-reset/complete/"


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
