"""Seed the database with a demo administrator, coach, athlete, exercise
library, a four-day program, calendar, sample logs, nutrition, and supplements.

Usage: python manage.py seed_demo [--flush-demo]
Default passwords are printed at the end (change them immediately on real
deployments; demo users are created with must_change_password=True except
the admin).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

EXERCISES = [
    # name, muscle, pattern, equipment, category, compound, focus
    ("Bench Press", "chest", "horizontal_push", "barbell", "strength", True, "strength"),
    ("Back Squat", "quads", "squat", "barbell", "strength", True, "strength"),
    ("Deadlift", "hamstrings", "hinge", "barbell", "strength", True, "strength"),
    ("Overhead Press", "shoulders", "vertical_push", "barbell", "strength", True, "strength"),
    ("Power Clean", "full_body", "hinge", "barbell", "power", True, "power"),
    ("Zercher Squat", "quads", "squat", "barbell", "strength", True, "strength"),
    ("Romanian Deadlift", "hamstrings", "hinge", "barbell", "hypertrophy", True, "hypertrophy"),
    ("Bulgarian Split Squat", "quads", "lunge", "dumbbell", "hypertrophy", True, "hypertrophy"),
    ("Lat Pulldown", "back", "vertical_pull", "cable", "hypertrophy", True, "hypertrophy"),
    ("Chest-Supported Row", "back", "horizontal_pull", "machine", "hypertrophy", True, "hypertrophy"),
    ("Leg Extension", "quads", "isolation_pattern", "machine", "hypertrophy", False, "hypertrophy"),
    ("Hamstring Curl", "hamstrings", "isolation_pattern", "machine", "hypertrophy", False, "hypertrophy"),
    ("Walking Lunge", "quads", "lunge", "dumbbell", "hypertrophy", True, "hypertrophy"),
    ("Sled Drag", "full_body", "locomotion", "sled", "conditioning", True, "mixed"),
    ("Cable Crunch", "core", "isolation_pattern", "cable", "core", False, "hypertrophy"),
    ("Landmine Rotation", "core", "rotation", "landmine", "core", False, "power"),
    ("Easy Run", "full_body", "locomotion", "bodyweight", "running", True, "mixed"),
]


class Command(BaseCommand):
    help = "Seed demo data: users, exercises, program, calendar, logs, nutrition, supplements."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush-demo", action="store_true",
            help="Delete previously seeded demo users (admin/coach/athlete) first.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from accounts.models import User
        from accounts.services import create_user_account
        from calendar_app.services.generation import generate_program_schedule
        from exercises.models import Exercise
        from nutrition.models import MacroRuleSet, NutritionTarget
        from profiles.models import AthleteProfile, Measurement
        from programs.models import Program, ProgramWeek, WorkoutDayTemplate, WorkoutExercise
        from progress.models import LiftMax
        from progress.services.records import detect_prs_for_session
        from supplements.defaults import DEFAULT_SUPPLEMENTS
        from supplements.models import Supplement, UserSupplementRecommendation
        from workouts.models import SetLog, WorkoutSession

        if options["flush_demo"]:
            User.objects.filter(username__in=["admin", "coach", "athlete"]).delete()
            self.stdout.write("Removed existing demo users.")

        # ------------------------------------------------------------- users
        if User.objects.filter(username="admin").exists():
            self.stdout.write(self.style.WARNING(
                "Demo users already exist — run with --flush-demo to recreate."
            ))
            return

        admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="admin-demo-pass-123",
            first_name="Site", last_name="Admin", is_coach=True,
            must_change_password=False,
        )
        AthleteProfile.objects.create(user=admin)
        coach, coach_password = create_user_account(
            username="coach", email="coach@example.com",
            first_name="Casey", last_name="Coach",
            is_coach=True, is_athlete=True,
            temporary_password="coach-demo-pass-123", created_by=admin,
        )
        athlete, athlete_password = create_user_account(
            username="athlete", email="athlete@example.com",
            first_name="Alex", last_name="Athlete",
            is_athlete=True, coach=coach,
            temporary_password="athlete-demo-pass-123", created_by=admin,
        )

        # --------------------------------------------------------- exercises
        exercise_map = {}
        for name, muscle, pattern, equipment, category, compound, focus in EXERCISES:
            exercise_map[name], _ = Exercise.objects.get_or_create(
                name=name,
                defaults=dict(
                    primary_muscle=muscle, movement_pattern=pattern,
                    equipment=equipment, exercise_category=category,
                    is_compound=compound, training_focus=focus,
                    created_by=admin,
                ),
            )

        # ------------------------------------------------------ measurements
        profile = athlete.athlete_profile
        profile.birth_date = date(1996, 5, 14)
        profile.sex_for_calculations = "male"
        profile.height_inches = Decimal("70")
        profile.current_weight_lb = Decimal("185")
        profile.goal_weight_lb = Decimal("178")
        profile.training_goal = "recomp"
        profile.training_experience = "intermediate"
        profile.activity_level = "moderate"
        profile.weekly_lifting_days = 4
        profile.weekly_running_days = 1
        profile.save()

        today = date.today()
        for weeks_ago, weight, waist in [(4, 188.0, 34.5), (3, 187.2, 34.4),
                                         (2, 186.4, 34.2), (1, 185.8, 34.1), (0, 185.0, 34.0)]:
            Measurement.objects.create(
                user=athlete, date=today - timedelta(weeks=weeks_ago),
                bodyweight_lb=Decimal(str(weight)), waist=Decimal(str(waist)),
                chest=Decimal("41.5"), neck=Decimal("15.5"),
                left_arm=Decimal("14.8"), right_arm=Decimal("15.0"),
                left_thigh=Decimal("23.5"), right_thigh=Decimal("23.6"),
                estimated_body_fat=Decimal("17.5"),
                measurement_method="tape", entered_by=coach,
            )

        # -------------------------------------------------------------- maxes
        for name, weight, reps, max_type in [
            ("Bench Press", 225, 1, "tested"), ("Back Squat", 315, 1, "tested"),
            ("Deadlift", 405, 1, "tested"), ("Overhead Press", 135, 3, "rep_max"),
        ]:
            LiftMax.objects.create(
                user=athlete, exercise=exercise_map[name], max_type=max_type,
                weight_lb=Decimal(weight), reps=reps,
                date=today - timedelta(days=30),
                bodyweight_at_time_lb=Decimal("187"), entered_by=coach,
            )

        # ------------------------------------------------------------ program
        program = Program.objects.create(
            owner=coach, name="Intermediate Upper/Lower — Block 1",
            description="Four-day upper/lower split, double progression on most lifts.",
            main_goal="hypertrophy", number_of_weeks=4,
            client_visible_notes="Leave 1–2 reps in reserve unless told otherwise. "
                                 "Warm up thoroughly before top sets.",
            coach_notes="Watch the left-knee valgus on squats.",
        )
        for number in range(1, 5):
            ProgramWeek.objects.create(
                program=program, week_number=number,
                deload=(number == 4),
                title=f"Week {number}" + (" (deload)" if number == 4 else ""),
            )

        day_specs = [
            ("Upper A", 0, [  # Monday
                ("Bench Press", 4, 6, 8, 185, 2, "double", None),
                ("Chest-Supported Row", 4, 8, 10, 115, 2, "double", None),
                ("Overhead Press", 3, 8, 10, 105, 2, "double", None),
                ("Lat Pulldown", 3, 10, 12, 140, 1, "double", "A"),
                ("Cable Crunch", 3, 12, 15, 90, 1, "rep", "A"),
            ]),
            ("Lower A", 1, [  # Tuesday
                ("Back Squat", 4, 5, 6, 265, 2, "double", None),
                ("Romanian Deadlift", 3, 8, 10, 225, 2, "double", None),
                ("Leg Extension", 3, 12, 15, 130, 1, "double", "A"),
                ("Hamstring Curl", 3, 12, 15, 110, 1, "double", "A"),
            ]),
            ("Upper B", 3, [  # Thursday
                ("Overhead Press", 4, 6, 8, 115, 2, "double", None),
                ("Lat Pulldown", 4, 8, 10, 150, 2, "double", None),
                ("Bench Press", 3, 10, 12, 155, 2, "fixed_load", None),
                ("Landmine Rotation", 3, 10, 12, 45, 1, "manual", None),
            ]),
            ("Lower B", 4, [  # Friday
                ("Deadlift", 3, 4, 6, 335, 2, "rir_rpe", None),
                ("Bulgarian Split Squat", 3, 8, 10, 50, 2, "double", None),
                ("Walking Lunge", 3, 10, 12, 40, 1, "rep", None),
                ("Sled Drag", 3, None, None, 135, None, "manual", None),
            ]),
        ]
        for week in program.weeks.all():
            for day_number, (day_name, weekday, exercises) in enumerate(day_specs, start=1):
                day = WorkoutDayTemplate.objects.create(
                    program_week=week, day_number=day_number, name=day_name,
                    default_weekday=weekday, order=day_number,
                    estimated_duration_minutes=65,
                    warmup_notes="5 min bike + 2 ramp-up sets on the first lift.",
                )
                for order, (ex_name, sets, rep_min, rep_max, weight, rir, method, superset) in enumerate(
                    exercises, start=1
                ):
                    WorkoutExercise.objects.create(
                        workout_day=day, exercise=exercise_map[ex_name], order=order,
                        target_sets=sets, target_rep_min=rep_min, target_rep_max=rep_max,
                        target_reps_text="" if rep_min else "20-40 yd",
                        target_weight_lb=Decimal(weight) if weight else None,
                        target_rir=Decimal(rir) if rir else None,
                        rest_seconds=150, progression_method=method,
                        superset_group=superset or "",
                        weight_increment_lb=Decimal("5"),
                    )

        # Assign: start this week's Monday so today falls inside week 1
        monday = today - timedelta(days=today.weekday())
        program.assign_to(athlete, assigned_by=coach, start_date=monday)

        # --------------------------------------------- one completed workout
        first_scheduled = athlete.scheduled_sessions.filter(
            workout_day__name="Upper A"
        ).order_by("date").first()
        session = WorkoutSession.objects.create(
            user=athlete, scheduled_session=first_scheduled,
            workout_day=first_scheduled.workout_day, program=program,
            date=first_scheduled.date, status="completed",
            completed_at=timezone.now(),
            energy=4, sleep_quality=4, soreness=2, stress=2, motivation=4,
            session_difficulty=7, pump_rating=4, performance_rating=4,
            notes="Felt strong. Bench moved well.",
        )
        for prescription in first_scheduled.workout_day.exercises.all():
            for set_number in range(1, prescription.target_sets + 1):
                SetLog.objects.create(
                    session=session, workout_exercise=prescription,
                    exercise=prescription.exercise, set_number=set_number,
                    weight_lb=prescription.target_weight_lb,
                    reps=prescription.target_rep_max or 10,
                    rir=prescription.target_rir, completed=True,
                )
        first_scheduled.status = "completed"
        first_scheduled.save(update_fields=["status"])
        detect_prs_for_session(session)
        from coaching.services.progression import generate_recommendations_for_session

        generate_recommendations_for_session(session)

        # ---------------------------------------------------------- nutrition
        MacroRuleSet.get_active()
        NutritionTarget.objects.create(
            user=athlete, goal="recomp", method="mifflin",
            maintenance_calories=2750, expected_weekly_change_lb=Decimal("-0.3"),
            calculated_calories=2600, calculated_protein_g=185,
            calculated_carbs_g=280, calculated_fat_g=75,
            calculated_fiber_g=36, calculated_water_oz=92,
            final_calories=2600, final_protein_g=190,
            pre_workout_suggestion="Meal with carbs + protein 1.5–2 h before training.",
            post_workout_suggestion="25–40 g protein within a couple of hours.",
            example_meals="Greek yogurt + berries; chicken burrito bowl; salmon, rice, broccoli.",
            coach_notes="Recomp phase: hold calories while the waist trend falls.",
            updated_by=coach,
        )

        # -------------------------------------------------------- supplements
        for spec in DEFAULT_SUPPLEMENTS:
            Supplement.objects.get_or_create(name=spec["name"], defaults={**spec, "created_by": admin})
        creatine = Supplement.objects.get(name="Creatine monohydrate")
        vitamin_d = Supplement.objects.get(name="Vitamin D3")
        UserSupplementRecommendation.objects.create(
            user=athlete, supplement=creatine, assigned_dose="5", dose_unit="g/day",
            timing="Any consistent time", frequency="Daily",
            reason="Standard maintenance protocol to support strength work.",
            start_date=today, entered_by=coach,
        )
        UserSupplementRecommendation.objects.create(
            user=athlete, supplement=vitamin_d, assigned_dose="1000", dose_unit="IU/day",
            timing="With breakfast", frequency="Daily (winter months)",
            reason="Limited sun exposure; conservative dose pending blood work.",
            start_date=today, entered_by=coach,
        )

        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write("Logins (change immediately on a real deployment):")
        self.stdout.write("  admin   / admin-demo-pass-123   (administrator, no forced change)")
        self.stdout.write(f"  coach   / {coach_password}   (must change at first login)")
        self.stdout.write(f"  athlete / {athlete_password}   (must change at first login)")
