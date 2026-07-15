import io
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class CleanupFilesCommandTests(TestCase):
    def test_dry_run_counts_orphans_without_deleting_them(self):
        with tempfile.TemporaryDirectory() as temporary_root:
            orphan = Path(temporary_root) / "imports" / "orphan.xlsx"
            orphan.parent.mkdir(parents=True)
            orphan.write_bytes(b"test")
            output = io.StringIO()

            with self.settings(PRIVATE_MEDIA_ROOT=temporary_root):
                call_command("cleanup_files", stdout=output)

            self.assertTrue(orphan.exists())
            self.assertIn("Orphaned files on disk: 1", output.getvalue())
            self.assertIn("Would delete 1 file(s).", output.getvalue())


class SeedDemoCommandTests(TestCase):
    def test_seed_demo_requires_explicit_production_override(self):
        with self.settings(DEBUG=False):
            with self.assertRaisesMessage(CommandError, "Refusing to create demo accounts"):
                call_command("seed_demo")
