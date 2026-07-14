from django.contrib import admin

from .models import Program, ProgramWeek, WorkoutDayTemplate, WorkoutExercise


class ProgramWeekInline(admin.TabularInline):
    model = ProgramWeek
    extra = 0


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "assigned_to", "status", "main_goal", "number_of_weeks")
    list_filter = ("status", "main_goal")
    search_fields = ("name", "assigned_to__username", "owner__username")
    autocomplete_fields = ("owner", "assigned_to")
    inlines = [ProgramWeekInline]


class WorkoutExerciseInline(admin.TabularInline):
    model = WorkoutExercise
    extra = 0
    autocomplete_fields = ("exercise",)


@admin.register(WorkoutDayTemplate)
class WorkoutDayTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "program_week", "day_number", "default_weekday")
    search_fields = ("name", "program_week__program__name")
    inlines = [WorkoutExerciseInline]


@admin.register(WorkoutExercise)
class WorkoutExerciseAdmin(admin.ModelAdmin):
    list_display = ("exercise", "workout_day", "target_sets", "progression_method")
    search_fields = ("exercise__name", "workout_day__name")
    autocomplete_fields = ("exercise", "workout_day")


@admin.register(ProgramWeek)
class ProgramWeekAdmin(admin.ModelAdmin):
    list_display = ("program", "week_number", "deload", "testing_week")
    search_fields = ("program__name",)
