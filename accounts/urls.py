"""URLs for authentication, profiles and role dashboards."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Authentication
    path("login/", views.EduManageLoginView.as_view(), name="login"),
    path("logout/", views.EduManageLogoutView.as_view(), name="logout"),
    path("logged-out/", views.LoggedOutView.as_view(), name="logged_out"),

    # Forgot / reset password
    path("password-reset/", views.EduManagePasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", views.EduManagePasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        views.EduManagePasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("password-reset/complete/", views.EduManagePasswordResetCompleteView.as_view(), name="password_reset_complete"),

    # Change password / profile
    path("password-change/", views.EduManagePasswordChangeView.as_view(), name="password_change"),
    path("password-change/done/", views.EduManagePasswordChangeDoneView.as_view(), name="password_change_done"),
    path("profile/", views.profile, name="profile"),

    # Role dashboards
    path("dashboard/", views.dashboard_redirect, name="dashboard"),
    path("dashboard/super-admin/", views.super_admin_dashboard, name="super_admin_dashboard"),
    path("dashboard/institute-admin/", views.institute_admin_dashboard, name="institute_admin_dashboard"),
    path("dashboard/teacher/", views.teacher_dashboard, name="teacher_dashboard"),
    path("dashboard/student/", views.student_dashboard, name="student_dashboard"),

    # Account management
    path("institutes/create/", views.institute_create, name="institute_create"),
    path("users/institute-admins/create/", views.institute_admin_create, name="institute_admin_create"),
    path("users/create/", views.role_user_create, name="role_user_create"),
    path("users/", views.user_list, name="user_list"),
    path("users/<int:pk>/activate/", views.set_user_active, {"active": True}, name="user_activate"),
    path("users/<int:pk>/deactivate/", views.set_user_active, {"active": False}, name="user_deactivate"),

    # Approved invitation flow (no public self-registration)
    path("invitations/create/", views.invitation_create, name="invitation_create"),
    path("register/<uuid:token>/", views.invitation_register, name="invitation_register"),
]
