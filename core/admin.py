from django.contrib import admin

from .models import AuditRecord


@admin.register(AuditRecord)
class AuditRecordAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp", "changed_by", "affected_user",
        "object_type", "field_changed",
    )
    list_filter = ("object_type",)
    search_fields = ("field_changed", "affected_user__username", "object_type")
    readonly_fields = [f.name for f in AuditRecord._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
