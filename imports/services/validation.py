"""Upload validation: extension + content sniffing + size limits.

No uploaded file is ever executed or parsed with macros/formulas enabled.
"""
import os
import zipfile

from django.conf import settings
from django.core.exceptions import ValidationError

XLSX_MAGIC = b"PK\x03\x04"  # xlsx is a zip container
PDF_MAGIC = b"%PDF-"

BLOCKED_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".sh", ".ps1", ".js", ".vbs", ".msi",
    ".com", ".scr", ".jar", ".apk", ".php", ".py", ".pl",
}


def _check_size(upload, max_mb, label):
    limit = max_mb * 1024 * 1024
    if upload.size > limit:
        raise ValidationError(f"{label} files must be {max_mb} MB or smaller.")
    if upload.size == 0:
        raise ValidationError("The uploaded file is empty.")


def _read_head(upload, length=8):
    upload.seek(0)
    head = upload.read(length)
    upload.seek(0)
    return head


def _extension(upload):
    ext = os.path.splitext(upload.name or "")[1].lower()
    if ext in BLOCKED_EXTENSIONS:
        raise ValidationError("This file type is not allowed.")
    return ext


def validate_excel_upload(upload):
    """Allow .xlsx (zip magic) and .csv (plain text). Reject legacy .xls/.xlsm."""
    ext = _extension(upload)
    _check_size(upload, settings.MAX_EXCEL_UPLOAD_MB, "Spreadsheet")
    head = _read_head(upload)
    if ext == ".xlsx":
        if not head.startswith(XLSX_MAGIC):
            raise ValidationError("This does not look like a valid .xlsx file.")
        try:
            upload.seek(0)
            with zipfile.ZipFile(upload) as archive:
                members = archive.infolist()
                names = {member.filename for member in members}
                total_uncompressed = sum(member.file_size for member in members)
                sheet_count = sum(
                    member.filename.startswith("xl/worksheets/sheet")
                    and member.filename.endswith(".xml")
                    for member in members
                )
                if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                    raise ValidationError("This does not look like a valid .xlsx workbook.")
                if len(members) > 2000 or sheet_count > 100:
                    raise ValidationError("This workbook contains too many internal files or worksheets.")
                limit = settings.MAX_EXCEL_UNCOMPRESSED_MB * 1024 * 1024
                if total_uncompressed > limit:
                    raise ValidationError(
                        "This workbook expands beyond the safe processing limit."
                    )
                if any(member.flag_bits & 0x1 for member in members):
                    raise ValidationError("Encrypted workbooks are not supported.")
        except zipfile.BadZipFile as error:
            raise ValidationError("This does not look like a valid .xlsx file.") from error
        finally:
            upload.seek(0)
    elif ext == ".csv":
        if b"\x00" in _read_head(upload, 1024):
            raise ValidationError("This does not look like a valid CSV text file.")
    else:
        raise ValidationError("Only .xlsx and .csv files are supported.")
    return ext


def validate_pdf_upload(upload):
    ext = _extension(upload)
    _check_size(upload, settings.MAX_PDF_UPLOAD_MB, "PDF")
    if ext != ".pdf" or not _read_head(upload, 5).startswith(PDF_MAGIC):
        raise ValidationError("Only PDF files are supported.")
    return ext


def validate_image_upload(upload):
    """Verify a real image with Pillow (guards against renamed executables)."""
    from PIL import Image, UnidentifiedImageError

    ext = _extension(upload)
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValidationError("Photos must be JPEG, PNG, or WebP.")
    _check_size(upload, settings.MAX_IMAGE_UPLOAD_MB, "Image")
    try:
        upload.seek(0)
        with Image.open(upload) as image:
            image.verify()
    except (UnidentifiedImageError, OSError):
        raise ValidationError("This does not look like a valid image file.")
    finally:
        upload.seek(0)
    return ext


def pdf_page_count(django_file):
    """Page count via pypdf; returns None if unreadable rather than failing."""
    from pypdf import PdfReader

    try:
        django_file.seek(0)
        reader = PdfReader(django_file)
        count = len(reader.pages)
        django_file.seek(0)
        return count
    except Exception:
        return None
