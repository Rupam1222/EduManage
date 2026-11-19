"""Audit trail for meaningful platform and institute actions."""

import re

from django.conf import settings
from django.db import models


class ActivityAction(models.TextChoices):
    """Canonical action names used by new audit call sites."""

    USER_LOGIN = "user_login", "User login"
    USER_LOGOUT = "user_logout", "User logout"
    STUDENT_CREATED = "student_created", "Student creation"
    TEACHER_CREATED = "teacher_created", "Teacher creation"
    NOTE_UPLOADED = "note_uploaded", "Notes upload"
    NOTE_DELETED = "note_deleted", "Notes deletion"
    ASSIGNMENT_CREATED = "assignment_created", "Assignment creation"
    ATTENDANCE_UPDATED = "attendance_updated", "Attendance update"
    FEE_PAYMENT = "fee_payment", "Fee payment"
    SUBSCRIPTION_CHANGED = "subscription_changed", "Subscription change"
    LICENSE_ACTIVATED = "license_activated", "License activation"
    PAYMENT_APPROVED = "payment_approved", "Payment approval"


_SENSITIVE_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|card[_-]?number|cvv|otp|authorization)\b\s*[:=]\s*([^\s,;]+)"
)


def redact_sensitive(value):
    """Never persist passwords, tokens, secrets or card data in audit text."""
    text = str(value or "")
    return _SENSITIVE_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)


class ActivityLog(models.Model):
    """A durable record of a meaningful platform action."""

    institute = models.ForeignKey(
        "institutes.Institute",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ("-timestamp",)

    def __str__(self):
        actor = self.user.email if self.user else "System"
        return f"{self.action} by {actor}"


def log_activity(request, action, description="", institute=None, user=None):
    """Create an audit entry from a request, tolerating missing metadata.

    Descriptions are redacted so credentials passed in by mistake can never be
    written to the audit trail. Pass a sensitive-free summary only.
    """
    actor = user
    if actor is None:
        actor = getattr(request, "user", None)
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None

    if institute is None and actor is not None:
        institute = getattr(actor, "institute", None)

    ip_address = None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "") if request else ""
    if forwarded:
        ip_address = forwarded.split(",")[0].strip() or None
    elif request:
        ip_address = request.META.get("REMOTE_ADDR") or None

    return ActivityLog.objects.create(
        user=actor,
        institute=institute,
        action=action,
        description=redact_sensitive(description),
        ip_address=ip_address,
    )


def log_fee_payment(request, description, institute=None, user=None):
    """Audit hook for the institute student-fee module."""
    return log_activity(
        request,
        ActivityAction.FEE_PAYMENT,
        description,
        institute=institute,
        user=user,
    )
