from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.services.access import can_view_client, coaches_client, is_administrator, is_coach
from core.services.storage import get_private_storage, sanitize_filename

from .models import ImportJob, ReferenceFile
from .services.excel_parser import (
    MAPPABLE_FIELDS,
    PREVIEW_ROWS,
    WorkbookLimitError,
    auto_parse_workbook,
    detect_header_row,
    list_sheets,
    parse_mapped_rows,
    read_rows,
    suggest_column_mapping,
)
from .services.program_builder import build_draft_program
from .services.validation import (
    pdf_page_count,
    validate_excel_upload,
    validate_pdf_upload,
)


def _upload_rate_limited(user):
    window_start = timezone.now() - timezone.timedelta(hours=1)
    count = (
        ImportJob.objects.filter(user=user, created_at__gte=window_start).count()
        + ReferenceFile.objects.filter(user=user, uploaded_at__gte=window_start).count()
    )
    return count >= settings.UPLOAD_RATE_LIMIT_PER_HOUR


class ExcelUploadForm(forms.Form):
    file = forms.FileField(label="Workout spreadsheet (.xlsx or .csv)")

    def clean_file(self):
        upload = self.cleaned_data["file"]
        validate_excel_upload(upload)
        return upload


class PdfUploadForm(forms.Form):
    file = forms.FileField(label="Reference PDF")

    def clean_file(self):
        upload = self.cleaned_data["file"]
        validate_pdf_upload(upload)
        return upload


def _try_smart_workbook_import(job):
    """Save an auto-detected multi-week workbook, or leave the job untouched."""
    try:
        parsed = auto_parse_workbook(job.uploaded_file, _job_extension(job))
    except WorkbookLimitError:
        raise
    except Exception:
        return False
    if not parsed:
        return False
    weeks = sorted({row["week"] for row in parsed})
    job.selected_sheet = f"Auto-detected {len(weeks)} workout sheet(s)"
    job.status = ImportJob.Status.MAPPING
    job.mapping_configuration = {"mode": "automatic_multi_sheet", "weeks": weeks}
    job.preview_data = parsed[:PREVIEW_ROWS]
    job.parsed_data = parsed
    job.save(update_fields=[
        "selected_sheet", "status", "mapping_configuration", "preview_data", "parsed_data",
    ])
    return True


@login_required
def my_files(request):
    return render(request, "imports/my_files.html", {
        "jobs": ImportJob.objects.filter(user=request.user),
        "pdfs": ReferenceFile.objects.filter(user=request.user),
        "excel_form": ExcelUploadForm(),
        "pdf_form": PdfUploadForm(),
        "max_excel_mb": settings.MAX_EXCEL_UPLOAD_MB,
        "max_pdf_mb": settings.MAX_PDF_UPLOAD_MB,
    })


@login_required
def coach_upload(request):
    """Let a coach import a workbook into their own draft programme library."""
    if not is_coach(request.user):
        raise PermissionDenied
    if request.method == "POST":
        if _upload_rate_limited(request.user):
            messages.error(request, "Upload limit reached — please try again later.")
            return redirect("imports:coach_upload")
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["file"]
            job = ImportJob.objects.create(
                user=request.user,
                uploaded_file=upload,
                original_filename=sanitize_filename(upload.name),
                file_size=upload.size,
            )
            try:
                smart_imported = _try_smart_workbook_import(job)
            except WorkbookLimitError as error:
                job.status = ImportJob.Status.ERROR
                job.error_message = str(error)
                job.save(update_fields=["status", "error_message"])
                messages.error(request, str(error))
                return redirect("imports:coach_upload")
            if smart_imported:
                messages.success(
                    request,
                    f"Detected {len({row['week'] for row in job.parsed_data})} workout weeks and "
                    f"{len(job.parsed_data)} exercises automatically.",
                )
                return redirect("imports:review_parsed", job_uuid=job.uuid)
            return redirect("imports:select_sheet", job_uuid=job.uuid)
    else:
        form = ExcelUploadForm()
    return render(request, "imports/coach_upload.html", {
        "form": form, "max_excel_mb": settings.MAX_EXCEL_UPLOAD_MB,
    })


@login_required
@require_POST
def upload_excel(request):
    if _upload_rate_limited(request.user):
        messages.error(request, "Upload limit reached — please try again later.")
        return redirect("imports:my_files")
    form = ExcelUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        for error in form.errors.get("file", []):
            messages.error(request, error)
        return redirect("imports:my_files")
    upload = form.cleaned_data["file"]
    job = ImportJob.objects.create(
        user=request.user,
        uploaded_file=upload,
        original_filename=sanitize_filename(upload.name),
        file_size=upload.size,
    )
    return redirect("imports:select_sheet", job_uuid=job.uuid)


@login_required
def select_sheet(request, job_uuid):
    job = get_object_or_404(ImportJob, uuid=job_uuid, user=request.user)
    if job.status not in (ImportJob.Status.UPLOADED, ImportJob.Status.MAPPING):
        return redirect("imports:job_detail", job_uuid=job.uuid)
    extension = "." + job.original_filename.rsplit(".", 1)[-1].lower()
    try:
        sheets = list_sheets(job.uploaded_file, extension)
    except Exception:
        job.status = ImportJob.Status.ERROR
        job.error_message = "Could not read the spreadsheet."
        job.save(update_fields=["status", "error_message"])
        messages.error(request, "Could not read the spreadsheet.")
        return redirect("imports:my_files")
    if request.method == "POST":
        sheet = request.POST.get("sheet", "")
        if sheet in sheets:
            job.selected_sheet = sheet
            job.status = ImportJob.Status.MAPPING
            job.save(update_fields=["selected_sheet", "status"])
            return redirect("imports:mapping", job_uuid=job.uuid)
        messages.error(request, "Please choose a worksheet.")
    return render(request, "imports/select_sheet.html", {"job": job, "sheets": sheets})


def _job_extension(job):
    return "." + job.original_filename.rsplit(".", 1)[-1].lower()


@login_required
def mapping(request, job_uuid):
    job = get_object_or_404(ImportJob, uuid=job_uuid, user=request.user)
    if job.status != ImportJob.Status.MAPPING:
        return redirect("imports:job_detail", job_uuid=job.uuid)
    if (
        request.method == "GET"
        and request.GET.get("manual") == "1"
        and job.mapping_configuration.get("mode") == "automatic_multi_sheet"
    ):
        job.selected_sheet = ""
        job.mapping_configuration = {"mode": "manual"}
        job.preview_data = []
        job.parsed_data = []
        job.save(update_fields=[
            "selected_sheet", "mapping_configuration", "preview_data", "parsed_data",
        ])
        messages.info(request, "Choose a worksheet to map manually.")
        return redirect("imports:select_sheet", job_uuid=job.uuid)
    if (
        job.parsed_data
        and job.mapping_configuration.get("mode") == "automatic_multi_sheet"
    ):
        return redirect("imports:review_parsed", job_uuid=job.uuid)
    if (
        request.method == "GET"
        and is_coach(request.user)
        and not job.parsed_data
        and job.mapping_configuration.get("mode") != "manual"
    ):
        try:
            smart_imported = _try_smart_workbook_import(job)
        except WorkbookLimitError as error:
            job.status = ImportJob.Status.ERROR
            job.error_message = str(error)
            job.save(update_fields=["status", "error_message"])
            messages.error(request, str(error))
            return redirect("imports:coach_upload")
        if smart_imported:
            messages.success(
                request,
                f"Detected {len({row['week'] for row in job.parsed_data})} workout weeks and "
                f"{len(job.parsed_data)} exercises automatically.",
            )
            return redirect("imports:review_parsed", job_uuid=job.uuid)
    try:
        rows = read_rows(job.uploaded_file, _job_extension(job), job.selected_sheet or None)
    except Exception:
        job.status = ImportJob.Status.ERROR
        job.error_message = "Could not read the selected worksheet."
        job.save(update_fields=["status", "error_message"])
        messages.error(request, "Could not read the selected worksheet.")
        return redirect("imports:my_files")
    if not rows:
        messages.error(request, "The selected worksheet is empty.")
        return redirect("imports:select_sheet", job_uuid=job.uuid)
    header_index, suggested_mapping = detect_header_row(rows)
    mapping_rows = rows[header_index:]
    header = mapping_rows[0]
    preview = mapping_rows[:PREVIEW_ROWS]

    if request.method == "POST":
        mapping_config = {}
        for field, _label in MAPPABLE_FIELDS:
            raw = request.POST.get(f"map_{field}", "")
            if raw.isdigit() and int(raw) < len(header):
                mapping_config[field] = int(raw)
        has_header = request.POST.get("has_header") == "on"
        parsed, errors = parse_mapped_rows(
            mapping_rows, mapping_config, has_header=has_header
        )
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            job.mapping_configuration = {
                "columns": mapping_config,
                "has_header": has_header,
                "header_row": header_index + 1,
            }
            job.preview_data = preview
            job.parsed_data = parsed
            job.save(update_fields=["mapping_configuration", "preview_data", "parsed_data"])
            return redirect("imports:review_parsed", job_uuid=job.uuid)

    return render(request, "imports/mapping.html", {
        "job": job,
        "header": header,
        "preview": preview,
        "fields": [
            (field, label, suggested_mapping.get(field))
            for field, label in MAPPABLE_FIELDS
        ],
        "columns": list(enumerate(header)),
    })


@login_required
def review_parsed(request, job_uuid):
    """Preview a mapped plan before client submission or coach draft creation."""
    job = get_object_or_404(ImportJob, uuid=job_uuid, user=request.user)
    if job.status != ImportJob.Status.MAPPING or not job.parsed_data:
        return redirect("imports:job_detail", job_uuid=job.uuid)
    coach_upload = is_coach(request.user)
    if request.method == "POST":
        if coach_upload:
            try:
                program = build_draft_program(job, coach=request.user)
            except ValueError as error:
                job.status = ImportJob.Status.ERROR
                job.error_message = str(error)
                job.save(update_fields=["status", "error_message"])
                messages.error(request, f"Import failed: {error}")
                return redirect("imports:coach_upload")
            messages.success(
                request,
                f"Draft program “{program.name}” created. Review it before assigning it.",
            )
            return redirect("programs:builder_detail", program_uuid=program.uuid)
        job.status = ImportJob.Status.SUBMITTED
        job.submitted_at = timezone.now()
        job.save(update_fields=["status", "submitted_at"])
        messages.success(
            request,
            "Submitted for coach approval. You'll see the result on this page.",
        )
        return redirect("imports:my_files")
    page_obj = Paginator(job.parsed_data, 100).get_page(request.GET.get("page"))
    return render(request, "imports/review_parsed.html", {
        "job": job,
        "rows": page_obj.object_list,
        "page_obj": page_obj,
        "total": len(job.parsed_data),
        "coach_upload": coach_upload,
    })


@login_required
def job_detail(request, job_uuid):
    job = get_object_or_404(ImportJob, uuid=job_uuid)
    if job.user_id != request.user.id and not can_view_client(request.user, job.user):
        raise Http404
    parsed_rows = job.parsed_data or []
    page_obj = Paginator(parsed_rows, 100).get_page(request.GET.get("page"))
    return render(request, "imports/job_detail.html", {
        "job": job,
        "rows": page_obj.object_list,
        "page_obj": page_obj,
        "total": len(parsed_rows),
    })


@login_required
@require_POST
def upload_pdf(request):
    if _upload_rate_limited(request.user):
        messages.error(request, "Upload limit reached — please try again later.")
        return redirect("imports:my_files")
    form = PdfUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        for error in form.errors.get("file", []):
            messages.error(request, error)
        return redirect("imports:my_files")
    upload = form.cleaned_data["file"]
    ReferenceFile.objects.create(
        user=request.user,
        file=upload,
        original_filename=sanitize_filename(upload.name),
        file_size=upload.size,
        page_count=pdf_page_count(upload),
    )
    messages.success(request, "PDF uploaded.")
    return redirect("imports:my_files")


@login_required
def download_pdf(request, file_uuid):
    reference = get_object_or_404(ReferenceFile, uuid=file_uuid)
    if reference.user_id != request.user.id and not can_view_client(request.user, reference.user):
        raise Http404
    storage = get_private_storage()
    if not storage.exists(reference.file.name):
        raise Http404
    response = FileResponse(
        storage.open(reference.file.name, "rb"), content_type="application/pdf"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{sanitize_filename(reference.original_filename)}"'
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def download_import_file(request, job_uuid):
    job = get_object_or_404(ImportJob, uuid=job_uuid)
    if job.user_id != request.user.id and not can_view_client(request.user, job.user):
        raise Http404
    storage = get_private_storage()
    if not job.uploaded_file or not storage.exists(job.uploaded_file.name):
        raise Http404
    response = FileResponse(storage.open(job.uploaded_file.name, "rb"))
    response["Content-Disposition"] = (
        f'attachment; filename="{sanitize_filename(job.original_filename)}"'
    )
    response["Cache-Control"] = "private, no-store"
    return response


# ------------------------------------------------------- coach file management

@login_required
def client_files(request, client_uuid):
    """Coach/admin view of one client's uploads (spreadsheets + PDFs)."""
    from core.services.access import get_client_or_404

    # This screen includes private coach notes, so the athlete's normal
    # self-view permission is intentionally not sufficient.
    client = get_client_or_404(request.user, client_uuid, manage=True)
    return render(request, "imports/client_files.html", {
        "client": client,
        "jobs": ImportJob.objects.filter(user=client),
        "pdfs": ReferenceFile.objects.filter(user=client),
    })


class ReferenceFileForm(forms.ModelForm):
    class Meta:
        model = ReferenceFile
        fields = ["coach_notes", "program"]
        widgets = {"coach_notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, athlete=None, coach=None, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q

        from programs.models import Program

        self.fields["program"].queryset = Program.objects.filter(
            Q(assigned_to=athlete)
            | Q(owner=coach, assigned_to__isnull=True)
        ).distinct()
        self.fields["program"].required = False


@login_required
def pdf_edit(request, file_uuid):
    """Coach attaches notes / links a PDF to a program. Clients cannot edit."""
    from core.services.access import get_client_or_404

    reference = get_object_or_404(ReferenceFile, uuid=file_uuid)
    client = get_client_or_404(request.user, reference.user.uuid, manage=True)
    form = ReferenceFileForm(
        request.POST or None, instance=reference,
        athlete=client, coach=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "File notes saved.")
        return redirect("imports:client_files", client_uuid=client.uuid)
    return render(request, "imports/pdf_edit.html", {
        "form": form, "reference": reference, "client": client,
    })


# ------------------------------------------------------------ coach approval

def _require_review_access(user, job):
    if is_administrator(user):
        return
    if not (user.is_coach and coaches_client(user, job.user)):
        raise PermissionDenied


@login_required
def approvals(request):
    if not is_coach(request.user):
        raise PermissionDenied
    jobs = ImportJob.objects.filter(status=ImportJob.Status.SUBMITTED).select_related("user")
    if not is_administrator(request.user):
        from coaching.models import CoachClientRelationship

        client_ids = CoachClientRelationship.objects.filter(
            coach=request.user, status=CoachClientRelationship.Status.ACTIVE
        ).values_list("client_id", flat=True)
        jobs = jobs.filter(user_id__in=client_ids)
    return render(request, "imports/approvals.html", {"jobs": jobs})


@login_required
@require_POST
def approve_job(request, job_uuid):
    job = get_object_or_404(ImportJob, uuid=job_uuid, status=ImportJob.Status.SUBMITTED)
    _require_review_access(request.user, job)
    job.status = ImportJob.Status.APPROVED
    job.reviewed_by = request.user
    job.reviewed_at = timezone.now()
    job.approval_notes = request.POST.get("notes", "")[:1000]
    job.save(update_fields=["status", "reviewed_by", "reviewed_at", "approval_notes"])
    try:
        program = build_draft_program(job, coach=request.user)
    except ValueError as error:
        job.status = ImportJob.Status.ERROR
        job.error_message = str(error)
        job.save(update_fields=["status", "error_message"])
        messages.error(request, f"Import failed: {error}")
        return redirect("imports:approvals")
    messages.success(
        request,
        f"Draft program “{program.name}” created. Review and edit it before assigning.",
    )
    return redirect("programs:builder_detail", program_uuid=program.uuid)


@login_required
@require_POST
def reject_job(request, job_uuid):
    job = get_object_or_404(ImportJob, uuid=job_uuid, status=ImportJob.Status.SUBMITTED)
    _require_review_access(request.user, job)
    job.status = ImportJob.Status.REJECTED
    job.reviewed_by = request.user
    job.reviewed_at = timezone.now()
    job.approval_notes = request.POST.get("notes", "")[:1000]
    job.save(update_fields=["status", "reviewed_by", "reviewed_at", "approval_notes"])
    messages.info(request, "Import rejected.")
    return redirect("imports:approvals")
