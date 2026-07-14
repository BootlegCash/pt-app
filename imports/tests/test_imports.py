import io

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.tests.utils import link_coach, make_user
from imports.models import ImportJob, ReferenceFile
from imports.services.excel_parser import parse_mapped_rows, parse_reps
from imports.services.validation import validate_excel_upload, validate_pdf_upload
from programs.models import Program


def make_xlsx(rows):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Plan"
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer.read()


SAMPLE_ROWS = [
    ["Week", "Day", "Workout", "Exercise", "Sets", "Reps", "Weight", "RIR", "Rest", "Notes"],
    [1, 1, "Upper A", "Bench Press", 4, "6-8", 185, 2, "2:30", "pause first rep"],
    [1, 1, "Upper A", "Chest-Supported Row", 4, "8–12", 115, 2, "90s", ""],
    [1, 2, "Lower A", "Back Squat", 3, "5", 265, 2, "3 min", ""],
    [1, 2, "Lower A", "Walking Lunge", 2, "10/leg", 40, "", "60", ""],
    [2, 1, "Upper A", "Bench Press", 4, "AMRAP", 185, 1, "150", ""],
]


class RepParsingTests(TestCase):
    def test_rep_formats(self):
        self.assertEqual(parse_reps("5"), {"min": 5, "max": 5, "text": ""})
        self.assertEqual(parse_reps("3-5"), {"min": 3, "max": 5, "text": ""})
        self.assertEqual(parse_reps("8–12"), {"min": 8, "max": 12, "text": ""})
        self.assertEqual(parse_reps("10/leg"), {"min": 10, "max": 10, "text": "10/leg"})
        self.assertEqual(parse_reps("AMRAP")["text"], "AMRAP")
        self.assertEqual(parse_reps("3 rounds")["text"], "3 rounds")
        self.assertEqual(parse_reps("20-40 yd")["text"], "20-40 yd")
        self.assertEqual(parse_reps("30 seconds")["text"], "30 seconds")
        self.assertEqual(parse_reps(""), {"min": None, "max": None, "text": ""})

    def test_mapping_requires_exercise_column(self):
        parsed, errors = parse_mapped_rows([["a", "b"]], {"sets": 0})
        self.assertEqual(parsed, [])
        self.assertTrue(errors)


class ValidationTests(TestCase):
    def test_rejects_wrong_extension(self):
        upload = SimpleUploadedFile("evil.exe", b"MZ....")
        with self.assertRaises(ValidationError):
            validate_excel_upload(upload)

    def test_rejects_renamed_binary_as_xlsx(self):
        upload = SimpleUploadedFile("fake.xlsx", b"not a zip file")
        with self.assertRaises(ValidationError):
            validate_excel_upload(upload)

    @override_settings(MAX_EXCEL_UPLOAD_MB=1)
    def test_rejects_oversize(self):
        upload = SimpleUploadedFile("big.csv", b"a," * 800_000)
        with self.assertRaises(ValidationError):
            validate_excel_upload(upload)

    def test_accepts_real_xlsx_and_csv(self):
        xlsx = SimpleUploadedFile("plan.xlsx", make_xlsx(SAMPLE_ROWS))
        self.assertEqual(validate_excel_upload(xlsx), ".xlsx")
        csv = SimpleUploadedFile("plan.csv", b"Exercise,Sets\nBench,3\n")
        self.assertEqual(validate_excel_upload(csv), ".csv")

    def test_pdf_validation(self):
        good = SimpleUploadedFile("doc.pdf", b"%PDF-1.7 fake body")
        self.assertEqual(validate_pdf_upload(good), ".pdf")
        bad = SimpleUploadedFile("doc.pdf", b"<html>nope</html>")
        with self.assertRaises(ValidationError):
            validate_pdf_upload(bad)


class ImportWorkflowTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user()
        link_coach(self.coach, self.athlete)
        self.client.force_login(self.athlete)

    def _upload(self):
        upload = SimpleUploadedFile("plan.xlsx", make_xlsx(SAMPLE_ROWS))
        self.client.post(reverse("imports:upload_excel"), {"file": upload})
        return ImportJob.objects.get(user=self.athlete)

    def _map_and_submit(self, job):
        self.client.post(reverse("imports:select_sheet", args=[job.uuid]), {"sheet": "Plan"})
        self.client.post(reverse("imports:mapping", args=[job.uuid]), {
            "map_week": "0", "map_day": "1", "map_workout_name": "2",
            "map_exercise": "3", "map_sets": "4", "map_reps": "5",
            "map_weight": "6", "map_rir": "7", "map_rest": "8", "map_notes": "9",
            "has_header": "on",
        })
        self.client.post(reverse("imports:review_parsed", args=[job.uuid]))
        job.refresh_from_db()
        return job

    def test_full_flow_to_submission(self):
        job = self._map_and_submit(self._upload())
        self.assertEqual(job.status, ImportJob.Status.SUBMITTED)
        self.assertEqual(len(job.parsed_data), 5)
        first = job.parsed_data[0]
        self.assertEqual(first["exercise"], "Bench Press")
        self.assertEqual(first["rep_min"], 6)
        self.assertEqual(first["rest_seconds"], 150)

    def test_approval_creates_draft_program_not_assignment(self):
        job = self._map_and_submit(self._upload())
        self.client.force_login(self.coach)
        response = self.client.post(
            reverse("imports:approve_job", args=[job.uuid]), {"notes": "looks good"}
        )
        self.assertEqual(response.status_code, 302)
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJob.Status.IMPORTED)
        program = job.created_program
        self.assertIsNotNone(program)
        self.assertEqual(program.status, Program.Status.DRAFT)
        self.assertIsNone(program.assigned_to)  # never auto-assigned
        self.assertEqual(program.number_of_weeks, 2)
        self.assertEqual(
            sum(w.days.count() for w in program.weeks.all()), 3
        )

    def test_rejection(self):
        job = self._map_and_submit(self._upload())
        self.client.force_login(self.coach)
        self.client.post(reverse("imports:reject_job", args=[job.uuid]), {"notes": "wrong file"})
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJob.Status.REJECTED)
        self.assertIsNone(job.created_program)

    def test_client_cannot_approve_own_upload(self):
        job = self._map_and_submit(self._upload())
        response = self.client.post(reverse("imports:approve_job", args=[job.uuid]))
        self.assertEqual(response.status_code, 403)

    def test_unrelated_coach_cannot_approve(self):
        job = self._map_and_submit(self._upload())
        stranger_coach = make_user(is_coach=True)
        self.client.force_login(stranger_coach)
        response = self.client.post(reverse("imports:approve_job", args=[job.uuid]))
        self.assertEqual(response.status_code, 403)


class PrivateFileAccessTests(TestCase):
    def setUp(self):
        self.coach = make_user(is_coach=True)
        self.athlete = make_user()
        self.stranger = make_user()
        link_coach(self.coach, self.athlete)
        self.client.force_login(self.athlete)
        self.client.post(reverse("imports:upload_pdf"), {
            "file": SimpleUploadedFile("notes.pdf", b"%PDF-1.7 body"),
        })
        self.pdf = ReferenceFile.objects.get(user=self.athlete)
        self.url = reverse("imports:download_pdf", args=[self.pdf.uuid])

    def test_owner_and_coach_can_download(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.client.force_login(self.coach)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_stranger_and_anonymous_cannot(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)  # to login

    def test_stored_filename_randomized(self):
        self.assertNotIn("notes", self.pdf.file.name)
        self.assertEqual(self.pdf.original_filename, "notes.pdf")
