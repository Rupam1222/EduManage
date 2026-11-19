from django.contrib import admin

from .models import Teacher, TeacherActivity


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("teacher_id", "full_name", "institute", "status")
    list_filter = ("status", "institute")
    search_fields = ("teacher_id", "full_name", "email", "mobile")
    filter_horizontal = ("subjects", "batches")
    readonly_fields = ("account",)


@admin.register(TeacherActivity)
class TeacherActivityAdmin(admin.ModelAdmin):
    list_display = ("teacher", "action", "actor", "created_at")
    list_filter = ("action",)
    search_fields = ("teacher__full_name", "teacher__teacher_id")
