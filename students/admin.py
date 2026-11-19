from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "student_id",
        "full_name",
        "institute",
        "course",
        "batch",
        "status",
    )
    list_filter = ("status", "institute", "course")
    search_fields = ("student_id", "full_name", "email", "mobile")
    readonly_fields = ("account",)
