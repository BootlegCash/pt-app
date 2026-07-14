from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from accounts.models import User
from core.services.access import can_view_client
from core.services.storage import get_private_storage
from progress.models import LiftMax
from progress.services.records import current_maxes_summary

from .models import AthleteProfile, Measurement
from .services import measurement_changes, navy_body_fat_estimate, symmetry_pairs


def _profile_context(user):
    profile = AthleteProfile.objects.filter(user=user).select_related(
        "current_program", "coach"
    ).first()
    latest = Measurement.objects.filter(user=user).first()
    previous = Measurement.objects.filter(user=user)[1:2]
    previous = previous[0] if previous else None
    navy = None
    if latest and profile and profile.height_inches and latest.neck and latest.waist:
        navy = navy_body_fat_estimate(
            sex=profile.sex_for_calculations,
            height_inches=profile.height_inches,
            neck=latest.neck, waist=latest.waist, hips=latest.hips,
        )
    return {
        "athlete": user,
        "profile": profile,
        "latest_measurement": latest,
        "previous_measurement": previous,
        "navy_estimate": navy,
        "maxes": current_maxes_summary(user),
    }


@login_required
def my_profile(request):
    return render(request, "profiles/profile.html", _profile_context(request.user))


@login_required
def my_measurements(request):
    user = request.user
    measurements = Measurement.objects.filter(user=user)
    latest = measurements.first()
    previous = measurements[1:2]
    previous = previous[0] if previous else None
    return render(request, "profiles/measurements.html", {
        "athlete": user,
        "measurements": measurements,
        "latest": latest,
        "changes": measurement_changes(latest, previous),
        "symmetry": symmetry_pairs(latest),
    })


@login_required
def profile_photo(request, user_uuid):
    """Serve a private profile photo only to the owner, admin, or their coach."""
    target = get_object_or_404(User, uuid=user_uuid)
    if not can_view_client(request.user, target):
        raise Http404
    profile = AthleteProfile.objects.filter(user=target).first()
    if not profile or not profile.profile_photo:
        raise Http404
    storage = get_private_storage()
    if not storage.exists(profile.profile_photo.name):
        raise Http404
    return FileResponse(storage.open(profile.profile_photo.name, "rb"))
