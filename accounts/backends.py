from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """Authenticate with either username or email address (case-insensitive)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except UserModel.DoesNotExist:
            # Run the hasher anyway to keep timing consistent.
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            user = UserModel.objects.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            ).order_by("id").first()
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
