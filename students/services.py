"""Server-side student lifecycle, enrollment and plan-limit enforcement."""

import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.models import Role
from activity_logs.models import ActivityAction, log_activity
from institutes.models import RegistrationStatus
from subscriptions.models import Subscription

from .models import Student, StudentStatus, split_full_name

User = get_user_model()


class StudentManagementError(Exception):
    """Base error for student administration operations."""


class NoActiveSubscription(StudentManagementError):
    """The institute has no subscription that currently grants access."""


class StudentLimitReached(StudentManagementError):
    """The active plan has no remaining student seats."""


class StudentAccountError(StudentManagementError):
    """A login account could not be created for the student."""


def active_subscription(institute):
    """Return the subscription that currently grants access, if any."""
    if institute is None:
        return None
    now = timezone.now()
    return (
        Subscription.all_objects.filter(
            institute=institute,
            status=RegistrationStatus.ACTIVE,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .select_related("plan")
        .order_by("-activated_at", "-requested_at")
        .first()
    )


def active_student_count(institute):
    """Count seats actually consumed by active students of this institute."""
    if institute is None:
        return 0
    return Student.all_objects.filter(
        institute=institute, status=StudentStatus.ACTIVE
    ).count()


def student_limit_context(institute):
    """Describe plan availability for templates and for create-time checks."""
    subscription = active_subscription(institute)
    used = active_student_count(institute)

    if subscription is None:
        return {
            "subscription": None,
            "limit": 0,
            "used": used,
            "remaining": 0,
            "unlimited": False,
            "can_create": False,
            "message": (
                "An active subscription is required to add students. Upgrade plan "
                "to restore student management."
            ),
        }

    limit = int(subscription.plan.max_students or 0)
    unlimited = limit <= 0
    remaining = None if unlimited else max(0, limit - used)
    can_create = unlimited or used < limit
    message = ""
    if not can_create:
        message = (
            f"Your {subscription.plan.plan_name} plan allows {limit} students and "
            f"all {limit} seats are in use. Upgrade plan to add more students."
        )
    return {
        "subscription": subscription,
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "unlimited": unlimited,
        "can_create": can_create,
        "message": message,
    }


def enforce_student_limit(institute):
    """Raise when the institute cannot add another student."""
    context = student_limit_context(institute)
    if context["subscription"] is None:
        raise NoActiveSubscription(context["message"])
    if not context["can_create"]:
        raise StudentLimitReached(context["message"])
    return context


def generate_enrollment_number(institute):
    """Generate a collision-resistant enrollment number for this tenant."""
    institute_code = (getattr(institute, "institute_id", "") or "").split("-")[-1]
    institute_code = institute_code[:4].upper() or "INST"
    prefix = f"STU-{institute_code}-{timezone.now().year}-"
    for _ in range(30):
        candidate = f"{prefix}{secrets.randbelow(900000) + 100000:06d}"
        if not Student.all_objects.filter(
            institute=institute, student_id=candidate
        ).exists():
            return candidate
    raise StudentManagementError("Unable to generate a unique enrollment number.")


def create_student_account(student, *, request=None, password=None):
    """Create a STUDENT login bound to the student's institute."""
    email = (student.email or "").strip().lower()
    if not email:
        raise StudentAccountError("An email address is required for the login account.")
    if User.objects.filter(email__iexact=email).exists():
        raise StudentAccountError(
            "A login account with this email already exists. Use a different email."
        )

    temporary_password = password or secrets.token_urlsafe(14)
    first_name, last_name = split_full_name(student.full_name)
    user = User.objects.create_user(
        email=email,
        password=temporary_password,
        first_name=first_name,
        last_name=last_name,
        role=Role.STUDENT,
        institute=student.institute,
        phone=student.mobile,
        is_active=student.status == StudentStatus.ACTIVE,
    )
    student.account = user
    return user, temporary_password


def send_student_welcome_email(user, request):
    """Email a one-time password-reset link; never email a stored password."""
    if not user.email or request is None:
        return
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = request.build_absolute_uri(
        reverse(
            "accounts:password_reset_confirm",
            kwargs={"uidb64": uid, "token": token},
        )
    )
    send_mail(
        "Your EduManage student account",
        (
            f"Hello {user.get_short_name()},\n\n"
            "An Institute Admin created a student login for you. Set your password "
            f"using this link: {reset_url}\n\n"
            "The link expires soon; use the Forgot Password page if needed."
        ),
        None,
        [user.email],
        fail_silently=True,
    )


def create_student_from_form(form, request):
    """Validate the plan, allocate an ID, save the student and create its login."""
    institute = request.user.institute
    if institute is None:
        raise StudentManagementError("Your account is not linked to an institute.")

    with transaction.atomic():
        enforce_student_limit(institute)
        student = form.save(commit=False)
        student.institute = institute
        student.student_id = generate_enrollment_number(institute)
        user, _ = create_student_account(student, request=request)
        student.save()
        log_activity(
            request,
            ActivityAction.STUDENT_CREATED,
            f"Created student {student.get_full_name()} ({student.student_id}).",
            institute=institute,
        )
        send_student_welcome_email(user, request)
    return student


def sync_student_account(student):
    """Keep the linked login in step with edited student details."""
    user = student.account
    if user is None:
        return None
    first_name, last_name = split_full_name(student.full_name)
    user.email = (student.email or "").strip().lower() or user.email
    user.first_name = first_name
    user.last_name = last_name
    user.phone = student.mobile
    user.is_active = student.status == StudentStatus.ACTIVE
    user.save()
    return user


def set_student_active(student, active):
    """Activate or deactivate both the student record and its login."""
    student.status = StudentStatus.ACTIVE if active else StudentStatus.INACTIVE
    student.save(update_fields=["status", "is_active", "updated_at"])
    return sync_student_account(student)


def delete_student(student):
    """Remove a student and the dedicated login account together."""
    user = student.account
    if user is not None and user.role != Role.STUDENT:
        user = None
    with transaction.atomic():
        student.delete()
        if user is not None:
            user.delete()


def filtered_students(institute, *, query="", status="", course_id="", batch_id=""):
    """Return only this institute's students matching the supplied filters."""
    queryset = Student.objects.for_institute(institute).select_related(
        "course", "batch", "account"
    )
    query = (query or "").strip()
    if query:
        queryset = queryset.filter(
            Q(student_id__icontains=query)
            | Q(full_name__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(mobile__icontains=query)
            | Q(parent_name__icontains=query)
        )
    if status in StudentStatus.values:
        queryset = queryset.filter(status=status)
    if str(course_id or "").isdigit():
        queryset = queryset.filter(course_id=int(course_id))
    if str(batch_id or "").isdigit():
        queryset = queryset.filter(batch_id=int(batch_id))
    return queryset
