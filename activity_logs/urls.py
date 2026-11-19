"""URLs for audit and activity logs."""

from django.urls import path

from . import views

app_name = "activity_logs"

urlpatterns = [
    path("", views.institute_activity_logs, name="institute_activity_logs"),
]
