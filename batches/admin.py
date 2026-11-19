from django.contrib import admin

from .models import Batch


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "code",
        "course",
        "assigned_teacher",
        "maximum_students",
        "student_count",
        "available_seats",
        "status",
    )
    list_filter = ("status", "institute", "course")
    search_fields = ("batch_name", "name", "code", "course__course_name", "course__name")
    filter_horizontal = ("subjects", "enrolled_students")
