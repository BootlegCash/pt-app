from django.contrib import admin

from .models import PainReport, SetLog, WorkoutSession


class SetLogInline(admin.TabularInline):
    model = SetLog
    extra = 0
    autocomplete_fields = ("exercise", "workout_exercise")


@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "date", "status", "duration_minutes")
    list_filter = ("status",)
    search_fields = ("user__username",)
    autocomplete_fields = ("user", "scheduled_session", "workout_day", "program")
    date_hierarchy = "date"
    inlines = [SetLogInline]


@admin.register(SetLog)
class SetLogAdmin(admin.ModelAdmin):
    list_display = ("session", "exercise", "set_number", "weight_lb", "reps", "completed")
    search_fields = ("exercise__name", "session__user__username")
    autocomplete_fields = ("session", "exercise", "workout_exercise")


@admin.register(PainReport)
class PainReportAdmin(admin.ModelAdmin):
    list_display = ("session", "body_location", "severity", "pain_type", "reviewed_by_coach")
    list_filter = ("pain_type", "reviewed_by_coach")
    autocomplete_fields = ("session", "exercise")
