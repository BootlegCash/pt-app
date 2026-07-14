from django.contrib import admin

from .models import AthleteProfile, Measurement


@admin.register(AthleteProfile)
class AthleteProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "training_goal", "coach", "current_program", "account_status")
    list_filter = ("training_goal", "account_status")
    search_fields = ("user__username", "user__email", "display_name")
    autocomplete_fields = ("user", "coach", "current_program")


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "bodyweight_lb", "waist", "estimated_body_fat")
    list_filter = ("measurement_method",)
    search_fields = ("user__username",)
    autocomplete_fields = ("user", "entered_by")
