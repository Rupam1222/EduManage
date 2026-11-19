"""Custom user, manager and invitation models for EduManage SaaS.

The user model uses email as its login identifier and is defined before the
first migration so ``AUTH_USER_MODEL`` never has to be swapped later.
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


def default_invitation_expiry():
    """Return the timestamp at which a new invitation expires."""
    return timezone.now() + timedelta(days=7)


class Role(models.TextChoices):
    """The four platform-wide roles supported by the SaaS."""

    SUPER_ADMIN = "super_admin", "Super Admin"
    INSTITUTE_ADMIN = "institute_admin", "Institute Admin"
    TEACHER = "teacher", "Teacher"
    STUDENT = "student", "Student"


class UserManager(BaseUserManager):
    """Manager that treats email as the unique login identifier."""

    use_in_migrations = True

    def _create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).strip().lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create a regular user. Default role is STUDENT."""
        extra_fields.setdefault("role", Role.STUDENT)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Create a fully privileged platform super administrator."""
        extra_fields.setdefault("role", Role.SUPER_ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("role") != Role.SUPER_ADMIN:
            raise ValueError("Superuser must have the SUPER_ADMIN role.")
        if not extra_fields.get("is_staff") or not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_staff and is_superuser set.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Project user model with role and institute scoping."""

    # Email replaces Django's default username field entirely.
    username = None
    email = models.EmailField("email address", unique=True)

    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True,
    )
    institute = models.ForeignKey(
        "institutes.Institute",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    phone = models.CharField(max_length=20, blank=True)
    profile_image = models.ImageField(
        upload_to="profiles/%Y/%m/%d/", blank=True, null=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    EMAIL_FIELD = "email"

    objects = UserManager()

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        swappable = "AUTH_USER_MODEL"
        ordering = ("email",)

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        """Return the concatenated first and last name."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_full_name(self):
        return self.full_name or self.email

    def get_short_name(self):
        return self.first_name or self.email.split("@")[0]

    @property
    def is_super_admin(self):
        return self.role == Role.SUPER_ADMIN

    @property
    def is_institute_admin(self):
        return self.role == Role.INSTITUTE_ADMIN

    @property
    def is_teacher(self):
        return self.role == Role.TEACHER

    @property
    def is_student(self):
        return self.role == Role.STUDENT


class Invitation(models.Model):
    """An approved, time-limited invitation to join as teacher or student.

    Teachers and students cannot self-register: an institute administrator must
    create one of these first. The token is single-use and expires after 7 days.
    """

    email = models.EmailField()
    role = models.CharField(
        max_length=32,
        choices=[
            (Role.TEACHER.value, Role.TEACHER.label),
            (Role.STUDENT.value, Role.STUDENT.label),
        ],
    )
    institute = models.ForeignKey(
        "institutes.Institute",
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_invitation_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Invitation for {self.email} ({self.role})"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return self.is_active and self.accepted_at is None and not self.is_expired

    def accept(self, user):
        """Mark this invitation as consumed by ``user``."""
        self.accepted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=["accepted_at", "is_active"])
