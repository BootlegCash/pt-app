from datetime import date as date_cls

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.services.access import get_client_or_404
from core.services.audit import record_form_changes
from profiles.models import AthleteProfile

from .forms import CalculatorForm, CheckinForm, TargetOverrideForm
from .models import MacroRuleSet, NutritionCheckin, NutritionTarget
from .services.calculator import calculate_targets
from .services.weight_trend import trend_recommendation, weekly_averages


@login_required
def my_nutrition(request):
    """Client-facing nutrition page (view + optional daily check-ins)."""
    target = NutritionTarget.objects.filter(user=request.user).first()
    today = date_cls.today()
    checkin = NutritionCheckin.objects.filter(user=request.user, date=today).first()
    return render(request, "nutrition/my_nutrition.html", {
        "target": target,
        "checkin": checkin,
        "today": today,
    })


@login_required
@require_POST
def checkin(request):
    form = CheckinForm(request.POST)
    if form.is_valid():
        NutritionCheckin.objects.update_or_create(
            user=request.user, date=date_cls.today(), defaults=form.cleaned_data
        )
        messages.success(request, "Check-in saved.")
    return redirect("nutrition:me")


@login_required
def coach_calculator(request, client_uuid):
    """Coach/administrator nutrition calculator + manual overrides for a client."""
    client = get_client_or_404(request.user, client_uuid, manage=True)
    profile = AthleteProfile.objects.filter(user=client).first()
    target, _ = NutritionTarget.objects.get_or_create(user=client)
    ruleset = MacroRuleSet.get_active()

    initial = {}
    if profile:
        initial = {
            "sex": profile.sex_for_calculations or AthleteProfile.Sex.MALE,
            "age": profile.age or 30,
            "height_inches": profile.height_inches,
            "weight_lb": profile.current_weight_lb,
            "activity_level": profile.activity_level,
            "occupation_activity": profile.occupation_activity,
            "weekly_lifting_days": profile.weekly_lifting_days,
            "weekly_cardio_days": profile.weekly_running_days,
            "goal": profile.training_goal if profile.training_goal in (
                "cut", "recomp", "maintain", "lean_bulk", "performance"
            ) else "maintain",
        }

    calc_form = CalculatorForm(
        request.POST if "calculate" in request.POST else None, initial=initial
    )
    override_form = TargetOverrideForm(
        request.POST if "save_overrides" in request.POST else None, instance=target
    )
    result = None

    if "calculate" in request.POST and calc_form.is_valid():
        data = calc_form.cleaned_data
        result = calculate_targets(
            sex=data["sex"], age=data["age"],
            height_inches=data["height_inches"], weight_lb=data["weight_lb"],
            activity_level=data["activity_level"],
            occupation_activity=data["occupation_activity"],
            weekly_lifting_days=data["weekly_lifting_days"],
            weekly_cardio_days=data["weekly_cardio_days"],
            goal=data["goal"], ruleset=ruleset,
            rate_lb_per_week=data.get("rate_lb_per_week"),
            body_fat_percent=data.get("body_fat_percent"),
            calorie_adjustment=data.get("calorie_adjustment") or 0,
            use_katch=data.get("use_katch", False),
        )
        if "apply" in request.POST:
            target.goal = data["goal"]
            target.method = result["method"]
            target.maintenance_calories = result["maintenance_calories"]
            target.expected_weekly_change_lb = result["expected_weekly_change_lb"]
            target.calculated_calories = result["calories"]
            target.calculated_protein_g = result["protein_g"]
            target.calculated_carbs_g = result["carbs_g"]
            target.calculated_fat_g = result["fat_g"]
            target.calculated_fiber_g = result["fiber_g"]
            target.calculated_water_oz = result["water_oz"]
            target.updated_by = request.user
            target.save()
            from core.services.audit import record_change

            record_change(
                changed_by=request.user, affected_user=client, obj=target,
                field="calculated_targets",
                previous="", new=f"{result['calories']} kcal ({data['goal']})",
                reason="Nutrition calculation applied",
            )
            messages.success(request, "Calculated targets saved for this client.")
            return redirect("nutrition:coach_calculator", client_uuid=client.uuid)

    if "save_overrides" in request.POST and override_form.is_valid():
        record_form_changes(
            changed_by=request.user, affected_user=client,
            form=override_form, reason="Nutrition target override",
        )
        target = override_form.save(commit=False)
        target.updated_by = request.user
        target.save()
        messages.success(request, "Final targets and guidance saved.")
        return redirect("nutrition:coach_calculator", client_uuid=client.uuid)

    return render(request, "nutrition/coach_calculator.html", {
        "client": client,
        "profile": profile,
        "target": target,
        "ruleset": ruleset,
        "calc_form": calc_form,
        "override_form": override_form,
        "result": result,
        "weekly": weekly_averages(client),
        "trend": trend_recommendation(client, target),
    })
