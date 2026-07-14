from django.contrib import admin

from .models import Exercise


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = (
        "name", "primary_muscle", "movement_pattern", "equipment",
        "exercise_category", "is_compound", "active",
    )
    list_filter = ("primary_muscle", "movement_pattern", "equipment", "exercise_category", "active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("substitutions",)
