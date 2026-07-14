from django.contrib import admin

from .models import ImportJob, ReferenceFile


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "user", "status", "created_at", "reviewed_by")
    list_filter = ("status",)
    search_fields = ("original_filename", "user__username")
    autocomplete_fields = ("user", "reviewed_by", "created_program")
    readonly_fields = ("preview_data", "parsed_data", "mapping_configuration")


@admin.register(ReferenceFile)
class ReferenceFileAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "user", "page_count", "file_size", "uploaded_at")
    search_fields = ("original_filename", "user__username")
    autocomplete_fields = ("user", "program")
