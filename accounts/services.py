"""Account provisioning. Only administrators create accounts (no public signup)."""
import secrets

from django.db import transaction


@transaction.atomic
def create_user_account(
    *,
    username,
    email,
    first_name="",
    last_name="",
    is_coach=False,
    is_athlete=True,
    temporary_password=None,
    active=True,
    coach=None,
    starting_program=None,
    created_by=None,
):
    """Create a user plus athlete profile, temp password, and optional coach link.

    Returns (user, temporary_password).
    """
    from accounts.models import User
    from coaching.models import CoachClientRelationship
    from core.services.audit import record_change
    from profiles.models import AthleteProfile

    temporary_password = temporary_password or secrets.token_urlsafe(9)
    user = User.objects.create_user(
        username=username,
        email=email,
        password=temporary_password,
        first_name=first_name,
        last_name=last_name,
        is_coach=is_coach,
        is_athlete=is_athlete,
        is_active=active,
        must_change_password=True,
    )
    profile = None
    if is_athlete:
        profile = AthleteProfile.objects.create(user=user, coach=coach)
    if coach is not None and is_athlete:
        CoachClientRelationship.objects.create(
            coach=coach, client=user, status=CoachClientRelationship.Status.ACTIVE
        )
    if starting_program is not None and profile is not None:
        starting_program.assign_to(user, assigned_by=created_by or coach)
    record_change(
        changed_by=created_by,
        affected_user=user,
        obj=user,
        field="account",
        previous="",
        new="created",
        reason="Administrator account creation",
    )
    return user, temporary_password
