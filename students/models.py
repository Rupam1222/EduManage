"""Tenant-scoped student records with a matching login account."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.tenant import TenantModel


class StudentStatus(models.TextChoices):
    """Lifecycle of a student record."""

    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    GRADUATED = "graduated", "Graduated"


class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"


def student_profile_picture_path(instance, filename):
    """Physically partition student uploads by tenant and enrollment number."""
    safe_name = str(filename).replace("\\", "/").rsplit("/", 1)[-1]
    return (
        f"tenants/{instance.institute_id}/students/"
        f"{instance.student_id or 'pending'}/profile/{safe_name}"
    )


def split_full_name(full_name):
    """Turn a full name into the first/last fields used by Django's User."""
    parts = (full_name or "").split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


class Student(TenantModel):
    """A student belonging to exactly one institute."""

    student_id = models.CharField(
        max_length=40,
        db_index=True,
        verbose_name="enrollment number",
    )
    account = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profile",
    )

    # Canonical identity fields. The older first_name/last_name/phone columns
    # remain in the schema for compatibility and are kept in sync on save.
    full_name = models.CharField(max_length=200, blank=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=16, choices=Gender.choices, blank=True, default=""
    )
    address = models.TextField(blank=True)
    parent_name = models.CharField(max_length=200, blank=True)
    parent_mobile = models.CharField(max_length=20, blank=True)
    qualification = models.CharField(max_length=200, blank=True)

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )
    batch = models.ForeignKey(
        "batches.Batch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )

    admission_date = models.DateField(default=timezone.localdate)
    profile_picture = models.ImageField(
        upload_to=student_profile_picture_path, blank=True, null=True
    )
    status = models.CharField(
        max_length=16,
        choices=StudentStatus.choices,
        default=StudentStatus.ACTIVE,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)

    search_fields = (
        "student_id",
        "full_name",
        "first_name",
        "last_name",
        "email",
        "mobile",
        "parent_name",
    )

    class Meta:
        ordering = ("full_name", "student_id")
        constraints = [
            models.UniqueConstraint(
                fields=("institute", "student_id"), name="unique_student_id_per_institute"
            )
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.student_id})"

    def save(self, *args, **kwargs):
        """Keep compatibility columns and the lifecycle flag synchronized."""
        self.full_name = (self.full_name or "").strip()
        if not self.full_name and (self.first_name or self.last_name):
            self.full_name = f"{self.first_name} {self.last_name}".strip()
        first, last = split_full_name(self.full_name)
        if first:
            self.first_name, self.last_name = first, last

        self.mobile = (self.mobile or "").strip()
        if not self.mobile:
            self.mobile = self.phone or ""
        self.phone = self.mobile

        if self.status not in StudentStatus.values:
            self.status = (
                StudentStatus.ACTIVE if self.is_active else StudentStatus.INACTIVE
            )
        self.is_active = self.status == StudentStatus.ACTIVE
        return super().save(*args, **kwargs)

    def clean(self):
        if self.batch and self.course and self.batch.course_id != self.course_id:
            raise ValidationError(
                {"batch": "This batch does not belong to the selected course."}
            )

    def get_full_name(self):
        return self.full_name or f"{self.first_name} {self.last_name}".strip()

    @property
    def name(self):
        """Read-only alias used by older templates."""
        return self.get_full_name()
