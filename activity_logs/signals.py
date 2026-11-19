"""Authentication signals that feed the audit trail."""

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import ActivityAction, log_activity


@receiver(user_logged_in)
def record_user_login(sender, request, user, **kwargs):
    if user is None or not getattr(user, "is_authenticated", False):
        return
    log_activity(
        request,
        ActivityAction.USER_LOGIN,
        f"{user.email} signed in.",
        institute=getattr(user, "institute", None),
        user=user,
    )


@receiver(user_logged_out)
def record_user_logout(sender, request, user, **kwargs):
    if user is None or not getattr(user, "is_authenticated", False):
        return
    log_activity(
        request,
        ActivityAction.USER_LOGOUT,
        f"{user.email} signed out.",
        institute=getattr(user, "institute", None),
        user=user,
    )
