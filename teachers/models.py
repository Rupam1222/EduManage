"""Tenant-scoped teacher records, assignments and activity history."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.tenant import TenantModel


class TeacherStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class TeacherActivityAction(models.TextChoices):
    CREATED = "created", "Created"
    UPDATED = "updated", "Updated"
    ACTIVATED = "activated", "Activated"
    DEACTIVATED = "deactivated", "Deactivated"
    MATERIAL_UPLOADED = "material_uploaded", "Study material uploaded"
    ASSIGNMENT_CREATED = "assignment_created", "Assignment created"
    ATTENDANCE_MARKED = "attendance_marked", "Attendance marked"
    MARKS_ENTERED = "marks_entered", "Examination marks entered"
    ANNOUNCEMENT_SENT = "announcement_sent", "Batch announcement sent"


def teacher_profile_picture_path(instance, filename):
    safe_name = str(filename).replace("\\", "/").rsplit("/", 1)[-1]
    return (
        f"tenants/{instance.institute_id}/teachers/"
        f"{instance.teacher_id or 'pending'}/profile/{safe_name}"
    )


def split_full_name(full_name):
    parts = (full_name or "").split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


class Teacher(TenantModel):
    """A teacher belonging to exactly one institute."""

    teacher_id = models.CharField(max_length=40, db_index=True)
    # Retained for compatibility with the earlier employee-number schema.
    employee_id = models.CharField(max_length=40, blank=True, db_index=True)
    account = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_profile",
    )

    full_name = models.CharField(max_length=200, blank=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    qualification = models.CharField(max_length=200, blank=True)
    experience = models.PositiveIntegerField(default=0)
    specialization = models.CharField(max_length=200, blank=True)
    joining_date = models.DateField(default=timezone.localdate)
    profile_picture = models.ImageField(
        upload_to=teacher_profile_picture_path, blank=True, null=True
    )
    status = models.CharField(
        max_length=16,
        choices=TeacherStatus.choices,
        default=TeacherStatus.ACTIVE,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)

    subjects = models.ManyToManyField(
        "courses.Subject", blank=True, related_name="teachers"
    )
    batches = models.ManyToManyField(
        "batches.Batch", blank=True, related_name="teachers"
    )

    search_fields = (
        "teacher_id",
        "full_name",
        "first_name",
        "last_name",
        "email",
        "mobile",
        "specialization",
    )

    class Meta:
        ordering = ("full_name", "teacher_id")
        constraints = [
            models.UniqueConstraint(
                fields=("institute", "employee_id"),
                name="unique_employee_id_per_institute",
            ),
            models.UniqueConstraint(
                fields=("institute", "teacher_id"), name="unique_teacher_id_per_institute"
            ),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.teacher_id})"

    def save(self, *args, **kwargs):
        self.full_name = (self.full_name or "").strip()
        if not self.full_name and (self.first_name or self.last_name):
            self.full_name = f"{self.first_name} {self.last_name}".strip()
        first, last = split_full_name(self.full_name)
        if first:
            self.first_name, self.last_name = first, last
        if not self.employee_id:
            self.employee_id = self.teacher_id

        self.mobile = (self.mobile or "").strip()
        if not self.mobile:
            self.mobile = self.phone or ""
        self.phone = self.mobile

        if self.status not in TeacherStatus.values:
            self.status = (
                TeacherStatus.ACTIVE if self.is_active else TeacherStatus.INACTIVE
            )
        self.is_active = self.status == TeacherStatus.ACTIVE
        return super().save(*args, **kwargs)

    def get_full_name(self):
        return self.full_name or f"{self.first_name} {self.last_name}".strip()

    @property
    def name(self):
        return self.get_full_name()


class TeacherActivity(TenantModel):
    """Append-only history of a teacher's administrative and workspace actions."""

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="activity"
    )
    action = models.CharField(max_length=32, choices=TeacherActivityAction.choices)
    notes = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_activity_entries",
    )

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_action_display()} — {self.teacher.get_full_name()}"
