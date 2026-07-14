"""Reusable authorization helpers.

Every private page must resolve its subject through these functions instead of
trusting IDs from URLs or forms.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404


def is_administrator(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def is_coach(user):
    return user.is_authenticated and (user.is_coach or is_administrator(user))


def coaches_client(coach, client):
    """True when `coach` has an ACTIVE relationship with `client`."""
    from coaching.models import CoachClientRelationship

    return CoachClientRelationship.objects.filter(
        coach=coach, client=client, status=CoachClientRelationship.Status.ACTIVE
    ).exists()


def can_view_client(viewer, client):
    """Owner, administrator, or actively-assigned coach."""
    if not viewer.is_authenticated:
        return False
    if viewer.pk == client.pk:
        return True
    if is_administrator(viewer):
        return True
    return viewer.is_coach and coaches_client(viewer, client)


def can_manage_client(viewer, client):
    """Administrators and actively-assigned coaches may edit prescriptions.
    The client themselves may NOT."""
    if not viewer.is_authenticated:
        return False
    if is_administrator(viewer):
        return True
    return viewer.is_coach and coaches_client(viewer, client)


def require_client_access(viewer, client, manage=False):
    check = can_manage_client if manage else can_view_client
    if not check(viewer, client):
        raise PermissionDenied("You do not have access to this athlete.")


def get_client_or_404(viewer, client_uuid, manage=False):
    """Resolve a client by UUID and enforce coach/admin authorization."""
    from accounts.models import User

    client = get_object_or_404(User, uuid=client_uuid)
    require_client_access(viewer, client, manage=manage)
    return client


class CoachRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_coach(self.request.user)


class AdministratorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_administrator(self.request.user)


class ClientAccessMixin(LoginRequiredMixin):
    """For coach views addressing a client via `client_uuid` URL kwarg."""

    manage_required = False

    def get_client(self):
        return get_client_or_404(
            self.request.user,
            self.kwargs["client_uuid"],
            manage=self.manage_required,
        )
