from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.services.access import get_client_or_404
from core.services.audit import record_change

from .models import EDUCATIONAL_DISCLAIMER, Supplement, UserSupplementRecommendation


@login_required
def my_supplements(request):
    recommendations = UserSupplementRecommendation.objects.filter(
        user=request.user, active=True
    ).select_related("supplement")
    return render(request, "supplements/my_supplements.html", {
        "recommendations": recommendations,
        "disclaimer": EDUCATIONAL_DISCLAIMER,
    })


class RecommendationForm(forms.ModelForm):
    class Meta:
        model = UserSupplementRecommendation
        fields = [
            "supplement", "assigned_dose", "dose_unit", "timing", "frequency",
            "reason", "start_date", "end_date", "coach_notes", "active",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 2}),
            "coach_notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplement"].queryset = Supplement.objects.filter(active=True)


@login_required
def coach_assign(request, client_uuid):
    client = get_client_or_404(request.user, client_uuid, manage=True)
    recommendations = UserSupplementRecommendation.objects.filter(
        user=client
    ).select_related("supplement")
    form = RecommendationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        recommendation = form.save(commit=False)
        recommendation.user = client
        recommendation.entered_by = request.user
        recommendation.save()
        record_change(
            changed_by=request.user, affected_user=client, obj=recommendation,
            field="supplement",
            previous="", new=f"{recommendation.supplement.name} {recommendation.assigned_dose}",
            reason="Supplement assignment",
        )
        messages.success(request, f"{recommendation.supplement.name} assigned.")
        return redirect("supplements:coach_assign", client_uuid=client.uuid)
    return render(request, "supplements/coach_assign.html", {
        "client": client,
        "recommendations": recommendations,
        "form": form,
    })


@login_required
@require_POST
def coach_toggle(request, rec_uuid):
    recommendation = get_object_or_404(UserSupplementRecommendation, uuid=rec_uuid)
    client = get_client_or_404(request.user, recommendation.user.uuid, manage=True)
    recommendation.active = not recommendation.active
    recommendation.save(update_fields=["active"])
    record_change(
        changed_by=request.user, affected_user=client, obj=recommendation,
        field="active", previous=not recommendation.active, new=recommendation.active,
        reason="Supplement recommendation toggled",
    )
    return redirect("supplements:coach_assign", client_uuid=client.uuid)
