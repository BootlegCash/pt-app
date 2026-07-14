from django.contrib import admin

from .models import MacroRuleSet, NutritionCheckin, NutritionTarget


@admin.register(MacroRuleSet)
class MacroRuleSetAdmin(admin.ModelAdmin):
    list_display = ("name", "active", "protein_g_per_lb", "fat_percent_calories", "updated_at")


@admin.register(NutritionTarget)
class NutritionTargetAdmin(admin.ModelAdmin):
    list_display = ("user", "goal", "maintenance_calories", "updated_at")
    search_fields = ("user__username",)
    autocomplete_fields = ("user", "updated_by")


@admin.register(NutritionCheckin)
class NutritionCheckinAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "calories_met", "protein_met", "water_met", "fiber_met")
    autocomplete_fields = ("user",)
