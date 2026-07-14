"""Shared factories for tests (plain functions, no external dependencies)."""
from datetime import date
from decimal import Decimal

from accounts.models import User
from coaching.models import CoachClientRelationship
from exercises.models import Exercise
from profiles.models import AthleteProfile
from programs.models import Program, ProgramWeek, WorkoutDayTemplate, WorkoutExercise

_counter = {"n": 0}


def unique():
    _counter["n"] += 1
    return _counter["n"]


def make_user(username=None, *, is_coach=False, is_athlete=True, is_staff=False,
              password="testpass-12345", must_change_password=False):
    n = unique()
    username = username or f"user{n}"
    user = User.objects.create_user(
        username=username, email=f"{username}@example.com", password=password,
        is_coach=is_coach, is_athlete=is_athlete, is_staff=is_staff,
        must_change_password=must_change_password,
    )
    if is_athlete:
        AthleteProfile.objects.create(user=user)
    return user


def make_admin(username=None):
    n = unique()
    return User.objects.create_superuser(
        username=username or f"admin{n}", email=f"admin{n}@example.com",
        password="adminpass-12345", must_change_password=False,
    )


def link_coach(coach, client, status=CoachClientRelationship.Status.ACTIVE):
    return CoachClientRelationship.objects.create(coach=coach, client=client, status=status)


def make_exercise(name=None, **kwargs):
    n = unique()
    defaults = dict(primary_muscle="chest", movement_pattern="horizontal_push",
                    equipment="barbell")
    defaults.update(kwargs)
    return Exercise.objects.create(name=name or f"Exercise {n}", **defaults)


def make_program(owner, *, weeks=1, days_per_week=1, exercise=None, **exercise_kwargs):
    """A minimal program with `weeks` weeks × `days_per_week` days × 1 exercise."""
    exercise = exercise or make_exercise()
    program = Program.objects.create(
        owner=owner, name=f"Program {unique()}", number_of_weeks=weeks,
    )
    for week_number in range(1, weeks + 1):
        week = ProgramWeek.objects.create(program=program, week_number=week_number)
        for day_number in range(1, days_per_week + 1):
            day = WorkoutDayTemplate.objects.create(
                program_week=week, day_number=day_number,
                name=f"Day {day_number}", default_weekday=day_number - 1,
                order=day_number,
            )
            defaults = dict(
                order=1, target_sets=3, target_rep_min=8, target_rep_max=12,
                target_weight_lb=Decimal("100"), target_rir=Decimal("2"),
                progression_method="double", weight_increment_lb=Decimal("5"),
            )
            defaults.update(exercise_kwargs)
            WorkoutExercise.objects.create(workout_day=day, exercise=exercise, **defaults)
    return program


def assign_program(program, athlete, coach=None, start_date=None):
    return program.assign_to(
        athlete, assigned_by=coach or program.owner,
        start_date=start_date or date.today(),
    )
