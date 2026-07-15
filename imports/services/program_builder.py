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
    from programs.models import (
        Program,
        ProgramWeek,
        ProgressionMethod,
        WorkoutDayTemplate,
        WorkoutExercise,
    )

    import_job = (
        ImportJob.objects.select_for_update()
        .select_related("created_program", "user")
        .get(pk=import_job.pk)
    )
    if import_job.created_program_id:
        if import_job.status != ImportJob.Status.IMPORTED:
            import_job.status = ImportJob.Status.IMPORTED
            import_job.save(update_fields=["status"])
        return import_job.created_program

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
                default_weekday=row.get("weekday"),
                order=row["day"],
            )

    from calendar_app.services.generation import suggested_weekdays

    for week_number, week in weeks.items():
        week_days = sorted(
            (day for (number, _day_number), day in days.items() if number == week_number),
            key=lambda day: (day.order, day.day_number),
        )
        guesses = suggested_weekdays(len(week_days))
        changed = []
        for index, day in enumerate(week_days):
            if day.default_weekday is None:
                day.default_weekday = guesses[index]
                changed.append(day)
        if changed:
            WorkoutDayTemplate.objects.bulk_update(changed, ["default_weekday"])

    order_counters = {}
    exercise_cache = {}
    for row in rows:
        day = days[(row["week"], row["day"])]
        exercise_name = row["exercise"].strip()
        cache_key = exercise_name.casefold()
        exercise = exercise_cache.get(cache_key)
        if exercise is None:
            existing = Exercise.objects.filter(name__iexact=exercise_name).first()
            if existing is None or existing.public or existing.created_by_id == coach.id:
                exercise, _created = Exercise.objects.get_or_create(
                    name__iexact=exercise_name,
                    defaults={
                        "name": exercise_name,
                        "primary_muscle": Exercise.Muscle.OTHER,
                        "public": False,
                        "created_by": coach,
                    },
                )
            else:
                # Exercise names are globally unique. Never attach a different
                # coach's private exercise (and its private cues) to this plan.
                suffix = f" ({coach.username})"
                candidate = f"{exercise_name[:120 - len(suffix)]}{suffix}"
                counter = 2
                while Exercise.objects.filter(name__iexact=candidate).exists():
                    numbered_suffix = f" ({coach.username} {counter})"
                    candidate = (
                        f"{exercise_name[:120 - len(numbered_suffix)]}{numbered_suffix}"
                    )
                    counter += 1
                exercise = Exercise.objects.create(
                    name=candidate,
                    primary_muscle=Exercise.Muscle.OTHER,
                    public=False,
                    created_by=coach,
                )
            exercise_cache[cache_key] = exercise
        order_counters[day.id] = order_counters.get(day.id, 0) + 1
        set_weights = row.get("set_weights", [])
        progression_method = ProgressionMethod.DOUBLE
        if set_weights or row["weight"] is not None:
            progression_method = ProgressionMethod.MANUAL
        elif row["percentage"] is not None:
            progression_method = ProgressionMethod.PERCENTAGE
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
            set_weight_targets_lb=set_weights,
            target_percentage=row["percentage"],
            target_rir=row["rir"],
            target_rpe=row["rpe"],
            progression_method=progression_method,
            rest_seconds=row["rest_seconds"],
            tempo=row["tempo"],
            client_visible_notes=row["notes"],
        )

    import_job.created_program = program
    import_job.status = ImportJob.Status.IMPORTED
    import_job.save(update_fields=["created_program", "status"])
    return program
