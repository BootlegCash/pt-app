import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user. Roles: administrator (is_staff/is_superuser), coach, athlete.

    A user may hold both the coach and athlete roles. Public registration does
    not exist; only administrators create accounts.
    """

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField("email address", unique=True)
    is_coach = models.BooleanField(
        default=False, help_text="Can be assigned clients and use the coach dashboard."
    )
    is_athlete = models.BooleanField(
        default=True, help_text="Has an athlete profile and training pages."
    )
    must_change_password = models.BooleanField(
        default=True,
        help_text="Forces a password change at next login (set for new accounts).",
    )

    class Meta:
        ordering = ["username"]

    @property
    def is_administrator(self):
        return self.is_staff or self.is_superuser

    @property
    def display_label(self):
        full = self.get_full_name()
        return full or self.username

    @property
    def initials(self):
        parts = [p for p in [self.first_name, self.last_name] if p]
        if parts:
            return "".join(p[0].upper() for p in parts)[:2]
        return self.username[:2].upper()


class LoginAttempt(models.Model):
    """Failed-login tracking for lightweight, DB-backed rate limiting."""

    username = models.CharField(max_length=254, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
