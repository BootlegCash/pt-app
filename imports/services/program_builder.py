"""Turn approved ImportJob parsed_data into a DRAFT program.

The draft is owned by the reviewing coach, never auto-assigned, and fully
editable in the program builder before any assignment happens.
"""
from django.db import transaction
from django.utils import timezone


@transaction.atomic
def build_draft_program(import_job, *, coach):
    from exercises.models import Exercise
    from imports.models import ImportJob
    from programs.models import Program, ProgramWeek, WorkoutDayTemplate, WorkoutExercise

    rows = import_job.parsed_data or []
    if not rows:
        raise ValueError("No parsed rows to import.")

    program = Program.objects.create(
        owner=coach,
        name=f"Imported: {import_job.original_filename[:80]}",
        description=(
            f"Created from an approved upload by {import_job.user.display_label} "
            f"on {timezone.now():%Y-%m-%d}. Review before assigning."
        ),
        status=Program.Status.DRAFT,
        number_of_weeks=max(row["week"] for row in rows),
    )

    weeks, days = {}, {}
    for row in rows:
        week_number = row["week"]
        if week_number not in weeks:
            weeks[week_number] = ProgramWeek.objects.create(
                program=program, week_number=week_number
            )
        day_key = (week_number, row["day"])
        if day_key not in days:
            days[day_key] = WorkoutDayTemplate.objects.create(
                program_week=weeks[week_number],
                day_number=row["day"],
                name=row["workout_name"] or f"Day {row['day']}",
                order=row["day"],
            )

    order_counters = {}
    for row in rows:
        day = days[(row["week"], row["day"])]
        exercise, _created = Exercise.objects.get_or_create(
            name__iexact=row["exercise"].strip(),
            defaults={
                "name": row["exercise"].strip(),
                "primary_muscle": Exercise.Muscle.OTHER,
                "public": False,
                "created_by": coach,
            },
        )
        order_counters[day.id] = order_counters.get(day.id, 0) + 1
        WorkoutExercise.objects.create(
            workout_day=day,
            exercise=exercise,
            order=order_counters[day.id],
            superset_group=row["superset"],
            target_sets=row["sets"],
            target_rep_min=row["rep_min"],
            target_rep_max=row["rep_max"],
            target_reps_text=row["rep_text"],
            target_weight_lb=row["weight"],
            target_percentage=row["percentage"],
            target_rir=row["rir"],
            target_rpe=row["rpe"],
            rest_seconds=row["rest_seconds"],
            tempo=row["tempo"],
            client_visible_notes=row["notes"],
        )

    import_job.created_program = program
    import_job.status = ImportJob.Status.IMPORTED
    import_job.save(update_fields=["created_program", "status"])
    return program
