from django.contrib import admin

from .models import Examination, Mark


@admin.register(Examination)
class ExaminationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "batch",
        "subject",
        "exam_date",
        "max_marks",
        "pass_percentage",
        "is_active",
    )
    list_filter = ("batch", "exam_date", "is_active")
    search_fields = ("title",)


@admin.register(Mark)
class MarkAdmin(admin.ModelAdmin):
    list_display = ("student", "examination", "marks", "result_status", "entered_by")
    search_fields = ("student__full_name", "remarks")
