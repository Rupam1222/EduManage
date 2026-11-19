from django.contrib import admin

from .models import Assignment, AssignmentSubmission


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "batch", "subject", "teacher", "issue_date", "due_date")
    list_filter = ("batch", "subject")
    search_fields = ("title", "description")


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "assignment",
        "status",
        "submitted_at",
        "marks",
        "evaluated_by",
    )
    list_filter = ("status", "assignment__batch")
    search_fields = ("student__full_name", "student__student_id", "feedback")
