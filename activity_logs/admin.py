from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "institute", "timestamp", "ip_address")
    list_filter = ("action", "institute")
    search_fields = ("action", "description", "user__email", "institute__institute_name")
    readonly_fields = ("timestamp",)
    date_hierarchy = "timestamp"
