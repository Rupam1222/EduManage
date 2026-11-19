"""Root URL configuration for EduManage SaaS.

Every application owns its own URLconf under ``<app>/urls.py``. Feature routes
are added there as each module is implemented.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    path("superadmin/", include("superadmin.urls")),
    path("institutes/", include("institutes.urls")),
    path("subscriptions/", include("subscriptions.urls")),
    path("payments/", include("payments.urls")),
    path("licenses/", include("licenses.urls")),
    path("students/", include("students.urls")),
    path("teachers/", include("teachers.urls")),
    path("courses/", include("courses.urls")),
    path("batches/", include("batches.urls")),
    path("study-material/", include("study_material.urls")),
    path("attendance/", include("attendance.urls")),
    path("assignments/", include("assignments.urls")),
    path("examinations/", include("examinations.urls")),
    path("fees/", include("fees.urls")),
    path("notifications/", include("notifications.urls")),
    path("reports/", include("reports.urls")),
    path("activity-logs/", include("activity_logs.urls")),
]

# Custom error pages (handlers must be strings, not callables, in Django).
handler400 = "core.views.error_400"
handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"

# In development Django serves uploaded media directly. Production uses the
# configured storage backend / web server.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
