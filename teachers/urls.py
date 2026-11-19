"""URLs for teacher management and the teacher workspace."""

from django.urls import path

from . import views

app_name = "teachers"

urlpatterns = [
    path("", views.teacher_list, name="teacher_list"),
    path("activity/", views.teacher_activity_list, name="teacher_activity"),
    path("create/", views.teacher_create, name="teacher_create"),
    path("my-batches/", views.my_batches, name="my_batches"),
    path("my-students/", views.my_students, name="my_students"),
    path("<int:pk>/", views.teacher_detail, name="teacher_detail"),
    path("<int:pk>/edit/", views.teacher_edit, name="teacher_edit"),
    path("<int:pk>/activate/", views.teacher_activate, name="teacher_activate"),
    path("<int:pk>/deactivate/", views.teacher_deactivate, name="teacher_deactivate"),
    path("<int:pk>/delete/", views.teacher_delete, name="teacher_delete"),
]
