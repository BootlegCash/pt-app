"""User data export: everything belonging to one athlete, as plain JSON."""
from django.db.models.fields.files import FieldFile
from django.forms.models import model_to_dict


def _serialize(qs, exclude=()):
    rows = []
    for obj in qs:
        data = model_to_dict(obj)
        for field in exclude:
            data.pop(field, None)
        for key, value in list(data.items()):
            if isinstance(value, FieldFile):
                data[key] = value.name or ""
            elif not isinstance(value, (str, int, float, bool, list, type(None))):
                data[key] = str(value)
        rows.append(data)
    return rows


def export_user_data(user):
    from calendar_app.models import ScheduledSession
    from imports.models import ImportJob, ReferenceFile
    from nutrition.models import NutritionCheckin, NutritionTarget
    from profiles.models import AthleteProfile, Measurement
    from progress.models import LiftMax, PersonalRecord
    from supplements.models import UserSupplementRecommendation
    from workouts.models import PainReport, SetLog, WorkoutSession

    profile = AthleteProfile.objects.filter(user=user).first()
    return {
        "account": {
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_joined": str(user.date_joined),
        },
        # Coach-private notes are intentionally excluded from client exports.
        "profile": _serialize(
            AthleteProfile.objects.filter(user=user), exclude=("general_notes",)
        ) if profile else [],
        "measurements": _serialize(Measurement.objects.filter(user=user)),
        "lift_maxes": _serialize(LiftMax.objects.filter(user=user)),
        "personal_records": _serialize(PersonalRecord.objects.filter(user=user)),
        "scheduled_sessions": _serialize(ScheduledSession.objects.filter(user=user)),
        "workout_sessions": _serialize(WorkoutSession.objects.filter(user=user)),
        "set_logs": _serialize(SetLog.objects.filter(session__user=user)),
        "pain_reports": _serialize(PainReport.objects.filter(session__user=user)),
        "nutrition_targets": _serialize(NutritionTarget.objects.filter(user=user)),
        "nutrition_checkins": _serialize(NutritionCheckin.objects.filter(user=user)),
        "supplement_recommendations": _serialize(
            UserSupplementRecommendation.objects.filter(user=user),
        ),
        "uploads": _serialize(ImportJob.objects.filter(user=user), exclude=("parsed_data", "preview_data")),
        "reference_files": _serialize(
            ReferenceFile.objects.filter(user=user), exclude=("coach_notes",)
        ),
    }
