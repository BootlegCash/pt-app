"""Deep-copy helpers for programs, weeks, days, and exercises."""
from django.db import transaction


def copy_exercise(workout_exercise, target_day, order=None):
    clone = workout_exercise
    clone.pk = None
    clone.id = None
    import uuid as uuid_mod

    clone.uuid = uuid_mod.uuid4()
    clone.workout_day = target_day
    if order is not None:
        clone.order = order
    clone.save()
    return clone


def copy_day(day, target_week, day_number=None):
    exercises = list(day.exercises.all())
    clone = day
    clone.pk = None
    clone.id = None
    clone.program_week = target_week
    if day_number is not None:
        clone.day_number = day_number
        clone.order = day_number
    clone.save()
    for exercise in exercises:
        copy_exercise(exercise, clone)
    return clone


def copy_week(week, target_program, week_number):
    days = list(week.days.all())
    clone = week
    clone.pk = None
    clone.id = None
    clone.program = target_program
    clone.week_number = week_number
    clone.save()
    for day in days:
        copy_day(day, clone)
    return clone


@transaction.atomic
def copy_program(program, *, owner, new_name=None):
    """Duplicate a full program as an unassigned draft owned by `owner`."""
    from programs.models import Program

    weeks = list(program.weeks.all())
    clone = Program.objects.get(pk=program.pk)
    clone.pk = None
    clone.id = None
    import uuid as uuid_mod

    clone.uuid = uuid_mod.uuid4()
    clone.owner = owner
    clone.assigned_to = None
    clone.status = Program.Status.DRAFT
    clone.start_date = None
    clone.name = new_name or f"{program.name} (copy)"
    clone.save()
    for week in weeks:
        copy_week(week, clone, week.week_number)
    return clone
