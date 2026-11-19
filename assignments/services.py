"""Assignment access, submission status and file helpers."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from study_material.services import content_type_for, validate_material_file

from .models import Assignment, AssignmentSubmission, SubmissionStatus


def validate_document(upload, *, required=True):
    """Validate an assignment or answer file using the shared document rules."""
    if not upload:
        if required:
            raise ValidationError("Please choose a file to upload.")
        return None
    return validate_material_file(upload)


def served_content_type(file_field):
    extension = file_field.name.rsplit(".", 1)[-1] if file_field.name else ""
    return content_type_for(extension)


def submissions_for(assignment):
    return (
        AssignmentSubmission.objects.for_institute(assignment.institute)
        .filter(assignment=assignment)
        .select_related("student", "evaluated_by")
    )


@transaction.atomic
def ensure_pending_submissions(assignment):
    """Create Pending rows for every student currently in the batch."""
    created = 0
    for student in assignment.batch.student_queryset():
        _, was_created = AssignmentSubmission.objects.get_or_create(
            institute=assignment.institute,
            assignment=assignment,
            student=student,
            defaults={"status": SubmissionStatus.PENDING},
        )
        created += int(was_created)
    return created


def get_or_create_submission(assignment, student):
    """Return a student's submission row, creating a Pending row if needed."""
    submission, _ = AssignmentSubmission.objects.get_or_create(
        institute=assignment.institute,
        assignment=assignment,
        student=student,
        defaults={"status": SubmissionStatus.PENDING},
    )
    return submission


def is_late(assignment, when=None):
    when = when or timezone.localdate()
    if not assignment.due_date:
        return False
    return when > assignment.due_date


def assignments_for_student(student):
    """Published assignments released to any batch the student belongs to."""
    return (
        Assignment.objects.for_institute(student.institute)
        .filter(is_active=True)
        .filter(Q(batch=student.batch) | Q(batch__in=student.enrolled_batches.all()))
        .select_related("course", "batch", "subject", "teacher")
        .distinct()
    )


def can_access_assignment(user, assignment):
    """Teacher owner or a student enrolled in the assignment's batch."""
    role = getattr(user, "role", None)
    if user.institute_id and assignment.institute_id != user.institute_id:
        return False
    if role == "teacher":
        return assignment.teacher_id == getattr(user.teacher_profile, "pk", None)
    if role == "student":
        student = getattr(user, "student_profile", None)
        return bool(
            student
            and student.institute_id == assignment.institute_id
            and assignment.batch.student_queryset().filter(pk=student.pk).exists()
        )
    return False
