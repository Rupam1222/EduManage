"""Server-side teacher lifecycle, plan limits and assignment scoping."""

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
from batches.models import Batch
from courses.models import Course, Subject
from students.models import Student
from students.services import active_subscription

from .models import (
    Teacher,
    TeacherActivity,
    TeacherActivityAction,
    TeacherStatus,
    split_full_name,
)

User = get_user_model()


class TeacherManagementError(Exception):
    """Base error for teacher administration operations."""


class NoActiveSubscription(TeacherManagementError):
    """The institute has no subscription that currently grants access."""


class TeacherLimitReached(TeacherManagementError):
    """The active plan has no remaining teacher seats."""


class TeacherAccountError(TeacherManagementError):
    """A login account could not be created for the teacher."""


def active_teacher_count(institute):
    if institute is None:
        return 0
    return Teacher.all_objects.filter(
        institute=institute, status=TeacherStatus.ACTIVE
    ).count()


def teacher_limit_context(institute):
    subscription = active_subscription(institute)
    used = active_teacher_count(institute)
    if subscription is None:
        return {
            "subscription": None,
            "limit": 0,
            "used": used,
            "remaining": 0,
            "unlimited": False,
            "can_create": False,
            "message": (
                "An active subscription is required to add teachers. Upgrade plan "
                "to restore teacher management."
            ),
        }
    limit = int(subscription.plan.max_teachers or 0)
    unlimited = limit <= 0
    remaining = None if unlimited else max(0, limit - used)
    can_create = unlimited or used < limit
    message = ""
    if not can_create:
        message = (
            f"Your {subscription.plan.plan_name} plan allows {limit} teachers and "
            f"all {limit} seats are in use. Upgrade plan to add more teachers."
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


def enforce_teacher_limit(institute):
    context = teacher_limit_context(institute)
    if context["subscription"] is None:
        raise NoActiveSubscription(context["message"])
    if not context["can_create"]:
        raise TeacherLimitReached(context["message"])
    return context


def generate_teacher_id(institute):
    code = (getattr(institute, "institute_id", "") or "").split("-")[-1]
    code = code[:4].upper() or "INST"
    prefix = f"TCH-{code}-{timezone.now().year}-"
    for _ in range(30):
        candidate = f"{prefix}{secrets.randbelow(900000) + 100000:06d}"
        if not Teacher.all_objects.filter(
            institute=institute, teacher_id=candidate
        ).exists():
            return candidate
    raise TeacherManagementError("Unable to generate a unique teacher ID.")


def create_teacher_account(teacher, *, request=None, password=None):
    email = (teacher.email or "").strip().lower()
    if not email:
        raise TeacherAccountError("An email address is required for the login account.")
    if User.objects.filter(email__iexact=email).exists():
        raise TeacherAccountError(
            "A login account with this email already exists. Use a different email."
        )
    temporary_password = password or secrets.token_urlsafe(14)
    first_name, last_name = split_full_name(teacher.full_name)
    user = User.objects.create_user(
        email=email,
        password=temporary_password,
        first_name=first_name,
        last_name=last_name,
        role=Role.TEACHER,
        institute=teacher.institute,
        phone=teacher.mobile,
        is_active=teacher.status == TeacherStatus.ACTIVE,
    )
    teacher.account = user
    return user, temporary_password


def send_teacher_welcome_email(user, request):
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
        "Your EduManage teacher account",
        (
            f"Hello {user.get_short_name()},\n\n"
            "An Institute Admin created a teacher login for you. Set your password "
            f"using this link: {reset_url}\n\n"
            "The link expires soon; use the Forgot Password page if needed."
        ),
        None,
        [user.email],
        fail_silently=True,
    )


def create_teacher_from_form(form, request):
    institute = request.user.institute
    if institute is None:
        raise TeacherManagementError("Your account is not linked to an institute.")
    with transaction.atomic():
        enforce_teacher_limit(institute)
        teacher = form.save(commit=False)
        teacher.institute = institute
        teacher.teacher_id = generate_teacher_id(institute)
        user, _ = create_teacher_account(teacher, request=request)
        teacher.save()
        form.save_m2m()
        log_activity(
            request,
            ActivityAction.TEACHER_CREATED,
            f"Created teacher {teacher.get_full_name()} ({teacher.teacher_id}).",
            institute=institute,
        )
        send_teacher_welcome_email(user, request)
        log_teacher_activity(
            teacher,
            TeacherActivityAction.CREATED,
            actor=request.user,
            notes=f"Created by {request.user.email}.",
        )
    return teacher


def sync_teacher_account(teacher):
    user = teacher.account
    if user is None:
        return None
    first_name, last_name = split_full_name(teacher.full_name)
    user.email = (teacher.email or "").strip().lower() or user.email
    user.first_name = first_name
    user.last_name = last_name
    user.phone = teacher.mobile
    user.is_active = teacher.status == TeacherStatus.ACTIVE
    user.save()
    return user


def set_teacher_active(teacher, active, actor=None):
    teacher.status = TeacherStatus.ACTIVE if active else TeacherStatus.INACTIVE
    teacher.save(update_fields=["status", "is_active", "updated_at"])
    sync_teacher_account(teacher)
    action = (
        TeacherActivityAction.ACTIVATED if active else TeacherActivityAction.DEACTIVATED
    )
    log_teacher_activity(teacher, action, actor=actor)


def delete_teacher(teacher):
    user = teacher.account
    if user is not None and user.role != Role.TEACHER:
        user = None
    with transaction.atomic():
        teacher.delete()
        if user is not None:
            user.delete()


def filtered_teachers(institute, *, query="", status="", subject_id="", batch_id=""):
    queryset = Teacher.objects.for_institute(institute).prefetch_related(
        "subjects", "batches"
    )
    query = (query or "").strip()
    if query:
        queryset = queryset.filter(
            Q(teacher_id__icontains=query)
            | Q(full_name__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(mobile__icontains=query)
            | Q(specialization__icontains=query)
        )
    if status in TeacherStatus.values:
        queryset = queryset.filter(status=status)
    if str(subject_id or "").isdigit():
        queryset = queryset.filter(subjects__pk=int(subject_id))
    if str(batch_id or "").isdigit():
        queryset = queryset.filter(batches__pk=int(batch_id))
    return queryset.distinct()


def teacher_for_user(user):
    """Return the teacher profile for a logged-in teacher, or None."""
    if not getattr(user, "is_authenticated", False) or user.role != Role.TEACHER:
        return None
    return getattr(user, "teacher_profile", None)


def assigned_batches(teacher):
    """Batches the teacher is actually assigned to, inside their own tenant."""
    if teacher is None:
        return Batch.objects.none()
    return Batch.objects.for_institute(teacher.institute).filter(teachers=teacher)


def assigned_subjects(teacher):
    if teacher is None:
        return Subject.objects.none()
    return Subject.objects.for_institute(teacher.institute).filter(teachers=teacher)


def assigned_courses(teacher):
    """Courses reachable through the teacher's assigned batches or subjects."""
    if teacher is None:
        return Course.objects.none()
    return (
        Course.objects.for_institute(teacher.institute)
        .filter(
            Q(pk__in=teacher.batches.values("course_id"))
            | Q(pk__in=teacher.subjects.values("course_id"))
        )
        .distinct()
    )


def assigned_students(teacher):
    if teacher is None:
        return Student.objects.none()
    return Student.objects.for_institute(teacher.institute).filter(
        batch__in=assigned_batches(teacher)
    )


def log_teacher_activity(teacher, action, *, actor=None, notes="", request=None):
    if teacher is None:
        return None
    if actor is None and request is not None:
        actor = request.user
    return TeacherActivity.objects.create(
        institute=teacher.institute,
        teacher=teacher,
        action=action,
        actor=actor,
        notes=notes,
    )
