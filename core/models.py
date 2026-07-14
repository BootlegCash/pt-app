from django.conf import settings
from django.db import models


class AuditRecord(models.Model):
    """History of coach/administrator changes to client-facing prescriptions.

    Clients never see these records; they surface in Django Admin and the
    coach dashboard only.
    """

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_changes_made",
    )
    affected_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="audit_records",
    )
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=64)
    field_changed = models.CharField(max_length=100)
    previous_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.object_type}.{self.field_changed} @ {self.timestamp:%Y-%m-%d}"
