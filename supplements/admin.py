from django.contrib import admin

from .models import Supplement, UserSupplementRecommendation


@admin.register(Supplement)
class SupplementAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "default_dose", "dose_unit", "active")
    list_filter = ("category", "active")
    search_fields = ("name",)


@admin.register(UserSupplementRecommendation)
class UserSupplementRecommendationAdmin(admin.ModelAdmin):
    list_display = ("user", "supplement", "assigned_dose", "frequency", "active")
    list_filter = ("active",)
    search_fields = ("user__username", "supplement__name")
    autocomplete_fields = ("user", "supplement", "entered_by")
