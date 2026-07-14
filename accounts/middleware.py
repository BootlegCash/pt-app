from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Redirect users flagged with must_change_password to the change form.

    Allows only the password-change page, logout, and static assets until the
    temporary password has been replaced.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.must_change_password:
            allowed = {
                reverse("accounts:force_password_change"),
                reverse("accounts:logout"),
            }
            path = request.path
            if path not in allowed and not path.startswith("/static/"):
                return redirect("accounts:force_password_change")
        return self.get_response(request)
