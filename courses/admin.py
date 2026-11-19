from django.contrib import admin

from .models import Course, Subject


class SubjectInline(admin.TabularInline):
    model = Subject
    extra = 0
    fields = ("subject_name", "subject_code", "is_active")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "code",
        "institute",
        "duration",
        "course_fee",
        "status",
    )
    list_filter = ("status", "institute")
    search_fields = ("course_name", "name", "code", "description")
    inlines = (SubjectInline,)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "subject_code",
        "course",
        "institute",
        "is_active",
    )
    list_filter = ("is_active", "institute")
    search_fields = ("subject_name", "name", "subject_code", "code")
