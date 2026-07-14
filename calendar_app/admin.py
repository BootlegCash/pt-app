from django.contrib import admin

from .models import ScheduledSession


@admin.register(ScheduledSession)
class ScheduledSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "date", "session_type", "status")
    list_filter = ("session_type", "status")
    search_fields = ("title", "user__username")
    autocomplete_fields = ("user", "program", "workout_day")
    date_hierarchy = "date"
