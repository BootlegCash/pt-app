from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.services.dashboards import athlete_dashboard_context


@login_required
def dashboard(request):
    context = athlete_dashboard_context(request.user)
    return render(request, "core/dashboard.html", context)


def privacy(request):
    return render(request, "core/privacy.html")


def terms(request):
    return render(request, "core/terms.html")


def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)
