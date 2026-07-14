import uuid

from django.conf import settings
from django.db import models

from core.services.storage import get_private_storage, randomized_name


def import_upload_path(instance, filename):
    return f"imports/{randomized_name(filename)}"


def pdf_upload_path(instance, filename):
    return f"pdfs/{randomized_name(filename)}"


class ImportJob(models.Model):
    """A client-uploaded spreadsheet moving through the coach-approval pipeline.

    Nothing a client uploads ever overwrites a live program: approval creates a
    DRAFT program that the coach edits and assigns explicitly.
    """

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        MAPPING = "mapping", "Mapping columns"
        SUBMITTED = "submitted", "Submitted for approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        IMPORTED = "imported", "Imported"
        ERROR = "error", "Error"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="import_jobs"
    )
    uploaded_file = models.FileField(
        upload_to=import_upload_path, storage=get_private_storage
    )
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    selected_sheet = models.CharField(max_length=100, blank=True)
    mapping_configuration = models.JSONField(default=dict, blank=True)
    preview_data = models.JSONField(default=list, blank=True)
    parsed_data = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UPLOADED)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="imports_reviewed",
    )
    approval_notes = models.TextField(blank=True)
    created_program = models.ForeignKey(
        "programs.Program", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="source_imports",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Import {self.original_filename} ({self.status})"


class ReferenceFile(models.Model):
    """A privately-stored PDF reference document (plan, protocol, report).

    PDFs are never auto-converted to workouts; a future draft-only extraction
    step can plug into the ImportJob pipeline.
    """

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reference_files"
    )
    file = models.FileField(upload_to=pdf_upload_path, storage=get_private_storage)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    program = models.ForeignKey(
        "programs.Program", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reference_files",
    )
    coach_notes = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.original_filename
