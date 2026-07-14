"""Safe spreadsheet parsing.

openpyxl runs with read_only=True and data_only=True: formulas are replaced by
their last cached values and macros are never executed. Rep strings like
"8–12", "10/leg", "AMRAP", or "30 seconds" are parsed defensively — anything
unrecognized is kept as text rather than rejected.
"""
import csv
import io
import re

MAPPABLE_FIELDS = [
    ("week", "Week"),
    ("day", "Day"),
    ("workout_name", "Workout name"),
    ("exercise", "Exercise"),
    ("sets", "Sets"),
    ("reps", "Reps"),
    ("weight", "Weight"),
    ("percentage", "Percentage"),
    ("rir", "RIR"),
    ("rpe", "RPE"),
    ("rest", "Rest"),
    ("tempo", "Tempo"),
    ("notes", "Notes"),
    ("superset", "Superset"),
]

MAX_ROWS = 2000
MAX_COLS = 40
PREVIEW_ROWS = 8


def list_sheets(django_file, extension):
    if extension == ".csv":
        return ["Sheet1"]
    from openpyxl import load_workbook

    django_file.seek(0)
    workbook = load_workbook(django_file, read_only=True, data_only=True)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


def read_rows(django_file, extension, sheet_name=None, limit=MAX_ROWS):
    """Rows as lists of strings, truncated to sane bounds."""
    rows = []
    if extension == ".csv":
        django_file.seek(0)
        text = django_file.read().decode("utf-8-sig", errors="replace")
        for index, row in enumerate(csv.reader(io.StringIO(text))):
            if index >= limit:
                break
            rows.append([str(cell).strip() for cell in row[:MAX_COLS]])
    else:
        from openpyxl import load_workbook

        django_file.seek(0)
        workbook = load_workbook(django_file, read_only=True, data_only=True)
        try:
            sheet = workbook[sheet_name] if sheet_name else workbook.active
            for index, row in enumerate(sheet.iter_rows(values_only=True)):
                if index >= limit:
                    break
                rows.append([
                    "" if cell is None else str(cell).strip()
                    for cell in row[:MAX_COLS]
                ])
        finally:
            workbook.close()
    return rows


def parse_reps(raw):
    """Parse a rep prescription into {min, max, text}.

    Handles: 5 | 3-5 | 8–12 | 10/leg | AMRAP | 3 rounds | 20-40 yd | 30 seconds
    Unrecognized formats keep the raw text so nothing is lost.
    """
    text = str(raw or "").strip()
    if not text:
        return {"min": None, "max": None, "text": ""}
    plain = text.replace("–", "-").replace("—", "-").lower()
    match = re.fullmatch(r"(\d+)", plain)
    if match:
        value = int(match.group(1))
        return {"min": value, "max": value, "text": ""}
    match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", plain)
    if match:
        low, high = sorted((int(match.group(1)), int(match.group(2))))
        return {"min": low, "max": high, "text": ""}
    match = re.fullmatch(r"(\d+)\s*/\s*(leg|side|arm)", plain)
    if match:
        value = int(match.group(1))
        return {"min": value, "max": value, "text": text}
    # AMRAP, rounds, distances, times, everything else: keep as text
    return {"min": None, "max": None, "text": text[:40]}


def _int_or_none(value, maximum=1000):
    try:
        number = int(float(str(value).strip()))
        return number if 0 < number <= maximum else None
    except (TypeError, ValueError):
        return None


def _float_or_none(value, maximum=5000):
    try:
        number = float(str(value).strip().replace("%", ""))
        return number if 0 <= number <= maximum else None
    except (TypeError, ValueError):
        return None


def _parse_rest(value):
    """Rest as seconds from '90', '90s', '2:00', '2 min'."""
    text = str(value or "").strip().lower()
    if not text:
        return None
    match = re.fullmatch(r"(\d+):(\d{2})", text)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(min|minutes|m)", text)
    if match:
        return int(float(match.group(1)) * 60)
    match = re.fullmatch(r"(\d+)\s*(s|sec|seconds)?", text)
    if match:
        return int(match.group(1))
    return None


def parse_mapped_rows(rows, mapping, has_header=True):
    """Apply a column mapping ({field: column_index}) to raw rows.

    Returns (parsed_rows, errors). Each parsed row is a plain dict ready to be
    stored in ImportJob.parsed_data.
    """
    parsed, errors = [], []
    start = 1 if has_header else 0
    exercise_column = mapping.get("exercise")
    if exercise_column is None:
        return [], ["An Exercise column mapping is required."]

    def cell(row, field):
        index = mapping.get(field)
        if index is None or index >= len(row):
            return ""
        return row[index]

    for line_number, row in enumerate(rows[start:], start=start + 1):
        exercise_name = str(cell(row, "exercise")).strip()
        if not exercise_name:
            continue
        reps = parse_reps(cell(row, "reps"))
        parsed.append({
            "row": line_number,
            "week": _int_or_none(cell(row, "week"), maximum=52) or 1,
            "day": _int_or_none(cell(row, "day"), maximum=14) or 1,
            "workout_name": str(cell(row, "workout_name")).strip()[:120],
            "exercise": exercise_name[:120],
            "sets": _int_or_none(cell(row, "sets"), maximum=30) or 3,
            "rep_min": reps["min"],
            "rep_max": reps["max"],
            "rep_text": reps["text"],
            "weight": _float_or_none(cell(row, "weight")),
            "percentage": _float_or_none(cell(row, "percentage"), maximum=200),
            "rir": _float_or_none(cell(row, "rir"), maximum=10),
            "rpe": _float_or_none(cell(row, "rpe"), maximum=10),
            "rest_seconds": _parse_rest(cell(row, "rest")),
            "tempo": str(cell(row, "tempo")).strip()[:20],
            "notes": str(cell(row, "notes")).strip()[:300],
            "superset": str(cell(row, "superset")).strip()[:5],
        })
    if not parsed:
        errors.append("No rows with an exercise name were found.")
    return parsed, errors
