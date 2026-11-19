"""Authentication backend that authenticates by email address."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Case-insensitive email/password authentication.

    Inactive accounts are rejected, which also enforces account deactivation.
    """

    def authenticate(self, request, email=None, password=None, **kwargs):
        UserModel = get_user_model()
        if email is None:
            email = kwargs.get("username")
        if not email:
            return None

        email = UserModel.objects.normalize_email(email).strip().lower()
        try:
            user = UserModel.objects.get(email__iexact=email)
        except UserModel.DoesNotExist:
            # Run the hasher to reduce timing differences between existing and
            # non-existing accounts.
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
