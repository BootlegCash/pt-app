"""Back up the SQLite database (and optionally list private media for copying).

Usage:
  python manage.py backup_db                 # writes backups/db-YYYYmmdd-HHMMSS.sqlite3
  python manage.py backup_db --output /path/to/dir

Uses the SQLite online-backup API so a live database is copied safely.
For PostgreSQL deployments use pg_dump instead (see README).
"""
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Safely back up the SQLite database file."

    def add_arguments(self, parser):
        parser.add_argument("--output", default=None, help="Directory for the backup file.")

    def handle(self, *args, **options):
        database = settings.DATABASES["default"]
        if "sqlite3" not in database["ENGINE"]:
            raise CommandError(
                "backup_db only supports SQLite. For PostgreSQL use pg_dump "
                "(see README > Backups)."
            )
        source_path = Path(database["NAME"])
        if not source_path.exists():
            raise CommandError(f"Database file not found: {source_path}")
        output_dir = Path(options["output"] or (settings.BASE_DIR / "backups"))
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
        target_path = output_dir / f"db-{stamp}.sqlite3"

        source = sqlite3.connect(str(source_path))
        target = sqlite3.connect(str(target_path))
        try:
            with target:
                source.backup(target)
        finally:
            source.close()
            target.close()
        self.stdout.write(self.style.SUCCESS(f"Backup written to {target_path}"))
        self.stdout.write(
            "Remember to also copy the private_media/ directory for a full backup."
        )
