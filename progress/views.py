from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render

from accounts.models import User
from core.services.access import can_view_client
from exercises.models import Exercise
from profiles.models import Measurement

from .models import LiftMax, PersonalRecord
from .services import charts as chart_service
from .services.records import current_maxes_summary
from .services.volume import volume_summary


@login_required
def maxes(request):
    return render(request, "progress/maxes.html", {
        "athlete": request.user,
        "summaries": current_maxes_summary(request.user, limit=20),
        "records": PersonalRecord.objects.filter(user=request.user)
        .select_related("exercise")[:50],
        "history": LiftMax.objects.filter(user=request.user)
        .select_related("exercise")[:50],
    })


@login_required
def charts_page(request):
    exercises = Exercise.objects.filter(
        set_logs__session__user=request.user
    ).distinct().order_by("name")
    return render(request, "progress/charts.html", {
        "athlete": request.user,
        "exercises": exercises,
        "measurement_fields": Measurement.CIRCUMFERENCE_FIELDS + ["estimated_body_fat"],
    })


@login_required
def volume_page(request):
    return render(request, "progress/volume.html", {
        "athlete": request.user,
        "summary": volume_summary(request.user),
    })


CHART_BUILDERS = {
    "bodyweight": lambda user, request: chart_service.bodyweight_chart(user),
    "adherence": lambda user, request: chart_service.adherence_chart(user),
    "volume": lambda user, request: chart_service.volume_chart(user),
    "readiness": lambda user, request: chart_service.readiness_chart(user),
    "running_pace": lambda user, request: chart_service.running_pace_chart(user),
    "prs": lambda user, request: chart_service.pr_timeline_chart(user),
}


@login_required
def chart_data(request, name):
    """JSON chart data. Own data by default; coaches may pass ?client=<uuid>."""
    subject = request.user
    client_uuid = request.GET.get("client")
    if client_uuid:
        subject = get_object_or_404(User, uuid=client_uuid)
        if not can_view_client(request.user, subject):
            raise Http404
    if name == "measurement":
        payload = chart_service.measurement_chart(subject, request.GET.get("field", "waist"))
    elif name == "e1rm":
        exercise = get_object_or_404(Exercise, slug=request.GET.get("exercise", ""))
        payload = chart_service.e1rm_chart(subject, exercise)
    elif name in CHART_BUILDERS:
        payload = CHART_BUILDERS[name](subject, request)
    else:
        raise Http404
    return JsonResponse(payload)
