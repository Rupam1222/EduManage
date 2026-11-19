"""URLs for institute-admin-only student management."""

from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("", views.student_list, name="student_list"),
    path("create/", views.student_create, name="student_create"),
    path("export/", views.student_export, name="student_export"),
    path("<int:pk>/", views.student_detail, name="student_detail"),
    path("<int:pk>/edit/", views.student_edit, name="student_edit"),
    path("<int:pk>/activate/", views.student_activate, name="student_activate"),
    path("<int:pk>/deactivate/", views.student_deactivate, name="student_deactivate"),
    path("<int:pk>/delete/", views.student_delete, name="student_delete"),
]
