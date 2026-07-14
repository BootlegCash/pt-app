"""Clean up private storage: abandoned imports, rejected files, orphans, old previews.

Usage:
  python manage.py cleanup_files            # dry run (reports only)
  python manage.py cleanup_files --apply    # actually delete
  python manage.py cleanup_files --apply --purge-imported
      also deletes source spreadsheets of successfully imported jobs
      (the structured program data is retained).
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Remove abandoned/rejected/orphaned private files and stale previews."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Delete instead of reporting.")
        parser.add_argument("--days", type=int, default=14,
                            help="Age (days) before an unfinished import is 'abandoned'.")
        parser.add_argument("--purge-imported", action="store_true",
                            help="Also delete source files of successfully imported jobs.")

    def handle(self, *args, **options):
        from imports.models import ImportJob, ReferenceFile
        from profiles.models import AthleteProfile

        apply_changes = options["apply"]
        cutoff = timezone.now() - timezone.timedelta(days=options["days"])
        deleted_files = 0

        def remove_file(field_file, label):
            nonlocal deleted_files
            if not field_file:
                return
            self.stdout.write(f"  {label}: {field_file.name}")
            if apply_changes:
                field_file.delete(save=False)
            deleted_files += 1

        # 1. Abandoned imports (never submitted, older than cutoff)
        abandoned = ImportJob.objects.filter(
            status__in=[ImportJob.Status.UPLOADED, ImportJob.Status.MAPPING],
            created_at__lt=cutoff,
        )
        self.stdout.write(f"Abandoned imports: {abandoned.count()}")
        for job in abandoned:
            remove_file(job.uploaded_file, "abandoned")
            if apply_changes:
                job.delete()

        # 2. Rejected imports: drop the file, keep the record for history
        rejected = ImportJob.objects.filter(
            status=ImportJob.Status.REJECTED
        ).exclude(uploaded_file="")
        self.stdout.write(f"Rejected imports with files: {rejected.count()}")
        for job in rejected:
            remove_file(job.uploaded_file, "rejected")
            if apply_changes:
                job.uploaded_file = ""
                job.preview_data = []
                job.save(update_fields=["uploaded_file", "preview_data"])

        # 3. Old previews on finished jobs
        finished = ImportJob.objects.filter(
            status__in=[ImportJob.Status.IMPORTED, ImportJob.Status.APPROVED]
        ).exclude(preview_data=[])
        self.stdout.write(f"Stale previews: {finished.count()}")
        if apply_changes:
            for job in finished:
                job.preview_data = []
                job.save(update_fields=["preview_data"])

        # 4. Optionally purge source files of imported jobs (data is in the DB)
        if options["purge_imported"]:
            imported = ImportJob.objects.filter(
                status=ImportJob.Status.IMPORTED
            ).exclude(uploaded_file="")
            self.stdout.write(f"Imported source files: {imported.count()}")
            for job in imported:
                remove_file(job.uploaded_file, "imported-source")
                if apply_changes:
                    job.uploaded_file = ""
                    job.save(update_fields=["uploaded_file"])

        # 5. Orphaned files on disk not referenced by any model
        referenced = set()
        for job in ImportJob.objects.exclude(uploaded_file=""):
            referenced.add(job.uploaded_file.name.replace("\\", "/"))
        for ref in ReferenceFile.objects.exclude(file=""):
            referenced.add(ref.file.name.replace("\\", "/"))
        for profile in AthleteProfile.objects.exclude(profile_photo=""):
            if profile.profile_photo:
                referenced.add(profile.profile_photo.name.replace("\\", "/"))
        root = settings.PRIVATE_MEDIA_ROOT
        orphans = []
        if os.path.isdir(root):
            for dirpath, _dirs, files in os.walk(root):
                for filename in files:
                    full = os.path.join(dirpath, filename)
                    relative = os.path.relpath(full, root).replace("\\", "/")
                    if relative not in referenced:
                        orphans.append(full)
        self.stdout.write(f"Orphaned files on disk: {len(orphans)}")
        for path in orphans:
            self.stdout.write(f"  orphan: {path}")
            if apply_changes:
                os.remove(path)
                deleted_files += 1

        verb = "Deleted" if apply_changes else "Would delete"
        self.stdout.write(self.style.SUCCESS(f"{verb} {deleted_files} file(s)."))
        if not apply_changes:
            self.stdout.write("Dry run only — re-run with --apply to delete.")
