from django.contrib import admin

from .models import LiftMax, PersonalRecord


@admin.register(LiftMax)
class LiftMaxAdmin(admin.ModelAdmin):
    list_display = ("user", "exercise", "max_type", "weight_lb", "reps", "estimated_1rm", "date")
    list_filter = ("max_type",)
    search_fields = ("user__username", "exercise__name")
    autocomplete_fields = ("user", "exercise", "entered_by")


@admin.register(PersonalRecord)
class PersonalRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "exercise", "record_type", "value", "date")
    list_filter = ("record_type",)
    search_fields = ("user__username", "exercise__name")
    autocomplete_fields = ("user", "exercise", "set_log")
