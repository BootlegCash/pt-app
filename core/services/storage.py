"""Private file storage behind a swappable backend.

`MEDIA_STORAGE_BACKEND=local` (default) keeps files under PRIVATE_MEDIA_ROOT,
outside any public URL. To add S3-compatible storage later, implement a
backend here and select it via the environment variable — callers only ever
use `get_private_storage()`.
"""
import os
import re
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage

_storage = None


def get_private_storage():
    global _storage
    backend = settings.MEDIA_STORAGE_BACKEND
    if _storage is None:
        if backend == "local":
            os.makedirs(settings.PRIVATE_MEDIA_ROOT, exist_ok=True)
            _storage = FileSystemStorage(location=str(settings.PRIVATE_MEDIA_ROOT))
        else:
            raise NotImplementedError(
                f"MEDIA_STORAGE_BACKEND={backend!r} is not implemented yet. "
                "Add an S3-compatible backend in core/services/storage.py."
            )
    return _storage


def sanitize_filename(name):
    base = os.path.basename(name or "file")
    base = re.sub(r"[^\w.\- ]", "_", base)
    return base[:120] or "file"


def randomized_name(original_name, prefix=""):
    """Random stored filename; the original name is kept in the DB only."""
    ext = os.path.splitext(sanitize_filename(original_name))[1].lower()
    return f"{prefix}{uuid.uuid4().hex}{ext}"
