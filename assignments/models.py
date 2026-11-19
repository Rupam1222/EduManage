"""Tenant-scoped assignments and student submissions."""

import uuid

from django.db import models
from django.utils import timezone

from core.tenant import TenantModel


ALLOWED_DOCUMENT_EXTENSIONS = {
    "pdf", "doc", "docx", "ppt", "pptx", "png", "jpg", "jpeg", "gif", "webp", "txt"
}


def _safe_filename(filename):
    return str(filename or "file").replace("\\", "/").rsplit("/", 1)[-1]


def assignment_upload_path(instance, filename):
    return (
        f"tenants/{instance.institute_id}/assignments/"
        f"{uuid.uuid4().hex}/{_safe_filename(filename)}"
    )


def submission_upload_path(instance, filename):
    return (
        f"tenants/{instance.institute_id}/assignment-submissions/"
        f"{uuid.uuid4().hex}/{_safe_filename(filename)}"
    )


class Assignment(TenantModel):
    """An assignment issued by a teacher to one assigned batch."""

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    issue_date = models.DateField(default=timezone.localdate)
    file = models.FileField(upload_to=assignment_upload_path, blank=True)
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="assignments"
    )
    subject = models.ForeignKey(
        "courses.Subject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments",
    )
    batch = models.ForeignKey(
        "batches.Batch", on_delete=models.CASCADE, related_name="assignments"
    )
    teacher = models.ForeignKey(
        "teachers.Teacher", on_delete=models.SET_NULL, null=True, related_name="assignments"
    )
    # Canonical deadline for the requested workflow. The historical name is kept
    # so existing teacher forms, tests and reports continue to work unchanged.
    due_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    search_fields = ("title", "description")

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title

    @property
    def deadline(self):
        return self.due_date

    @property
    def is_published(self):
        return self.is_active

    @property
    def file_extension(self):
        return (self.file.name.rsplit(".", 1)[-1] if self.file.name else "").lower()


class SubmissionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUBMITTED = "submitted", "Submitted"
    LATE = "late", "Late"
    EVALUATED = "evaluated", "Evaluated"


class AssignmentSubmission(TenantModel):
    """One student's answer file and evaluation for one assignment."""

    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        "students.Student", on_delete=models.CASCADE, related_name="assignment_submissions"
    )
    file = models.FileField(upload_to=submission_upload_path, blank=True)
    status = models.CharField(
        max_length=16, choices=SubmissionStatus.choices, default=SubmissionStatus.PENDING
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_late = models.BooleanField(default=False)
    marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    evaluated_by = models.ForeignKey(
        "teachers.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluated_submissions",
    )

    search_fields = ("student__full_name", "student__student_id", "feedback")

    class Meta:
        ordering = ("-submitted_at", "student__full_name")
        constraints = [
            models.UniqueConstraint(
                fields=("assignment", "student"),
                name="unique_submission_per_assignment_student",
            )
        ]

    def __str__(self):
        return f"{self.student.get_full_name()} — {self.assignment.title}"

    @property
    def is_pending(self):
        return self.status == SubmissionStatus.PENDING

    @property
    def is_evaluated(self):
        return self.status == SubmissionStatus.EVALUATED

    @property
    def file_extension(self):
        return (self.file.name.rsplit(".", 1)[-1] if self.file.name else "").lower()
