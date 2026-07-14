from django.contrib import admin

from .models import CoachClientRelationship, ProgressionRecommendation


@admin.register(CoachClientRelationship)
class CoachClientRelationshipAdmin(admin.ModelAdmin):
    list_display = ("coach", "client", "status", "created_at", "activated_at", "ended_at")
    list_filter = ("status",)
    search_fields = ("coach__username", "client__username")
    autocomplete_fields = ("coach", "client")


@admin.register(ProgressionRecommendation)
class ProgressionRecommendationAdmin(admin.ModelAdmin):
    list_display = ("user", "workout_exercise", "action", "amount_lb", "status", "created_at")
    list_filter = ("action", "status")
    search_fields = ("user__username", "workout_exercise__exercise__name")
    autocomplete_fields = ("user", "workout_exercise", "source_session", "reviewed_by")
