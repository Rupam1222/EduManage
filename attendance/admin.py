from django.contrib import admin

from .models import AttendanceRecord


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "batch",
        "date",
        "status",
        "teacher",
        "marked_by",
        "remarks",
    )
    list_filter = ("status", "date", "batch")
    search_fields = ("student__full_name", "student__student_id", "remarks")
