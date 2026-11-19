"""Authentication, profile and role-scoped dashboard views."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from institutes.models import Institute

from .decorators import (
    institute_admin_required,
    management_required,
    role_required,
    super_admin_required,
)
from .forms import (
    InstituteAdminCreateForm,
    InstituteForm,
    InvitationForm,
    InvitationRegisterForm,
    LoginForm,
    ProfileForm,
    RoleUserCreateForm,
)
from .models import Invitation, Role

User = get_user_model()

ROLE_DASHBOARD_URLS = {
    Role.SUPER_ADMIN: "superadmin:dashboard",
    Role.INSTITUTE_ADMIN: "accounts:institute_admin_dashboard",
    Role.TEACHER: "accounts:teacher_dashboard",
    Role.STUDENT: "accounts:student_dashboard",
}


def dashboard_url_for(user):
    """Return the dashboard URL appropriate for ``user``'s role."""
    return reverse(ROLE_DASHBOARD_URLS.get(user.role, "core:home"))


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------
class EduManageLoginView(LoginView):
    """Email login that redirects each role to its own dashboard."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return dashboard_url_for(self.request.user)


class EduManageLogoutView(LogoutView):
    """POST-only logout that flushes the session and shows a confirmation."""

    next_page = reverse_lazy("accounts:logged_out")


class LoggedOutView(TemplateView):
    """Confirmation shown after the session has been flushed."""

    template_name = "accounts/logged_out.html"


# ---------------------------------------------------------------------------
# Password reset and change
# ---------------------------------------------------------------------------
class EduManagePasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/email/password_reset_email.html"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class EduManagePasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class EduManagePasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class EduManagePasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


class EduManagePasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = "accounts/password_change_form.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        from django.contrib.sessions.models import Session

        response = super().form_valid(form)
        # Keep the current session (PasswordChangeView updates its auth hash)
        # but revoke every other active session for this account.
        current_key = self.request.session.session_key
        for session in Session.objects.all():
            if session.session_key == current_key:
                continue
            try:
                data = session.get_decoded()
            except Exception:
                session.delete()
                continue
            if str(data.get("_auth_user_id")) == str(self.request.user.pk):
                session.delete()
        return response


class EduManagePasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
@login_required
def profile(request):
    """View and update the signed-in user's own profile."""
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)

    return render(
        request,
        "accounts/profile.html",
        {"form": form, "profile_user": request.user},
    )


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------
@login_required
def dashboard_redirect(request):
    """Send each role to its own protected dashboard."""
    return redirect(dashboard_url_for(request.user))


def _render_dashboard(request, title, description, links, stats=None):
    layout = (
        "layouts/teacher_base.html"
        if request.user.role == Role.TEACHER
        else "layouts/student_base.html"
    )
    return render(
        request,
        "accounts/dashboard.html",
        {
            "dashboard_title": title,
            "dashboard_description": description,
            "dashboard_links": links,
            "dashboard_stats": stats or {},
            "dashboard_layout": layout,
        },
    )


@super_admin_required
def super_admin_dashboard(request):
    """Keep the legacy URL working while routing owners to the new console."""
    return redirect("superadmin:dashboard")


@institute_admin_required
def institute_admin_dashboard(request):
    """Tenant-scoped command centre with live counters and charts."""
    from .dashboard_data import institute_dashboard_context

    institute = request.user.institute
    return render(
        request,
        "accounts/institute_admin_dashboard.html",
        institute_dashboard_context(institute),
    )


@role_required(Role.TEACHER)
def teacher_dashboard(request):
    return _render_dashboard(
        request,
        "Teacher Dashboard",
        "Your teaching workspace. Academic modules are added in later phases.",
        [
            {
                "label": "My profile",
                "url": reverse("accounts:profile"),
                "description": "Update contact details and profile image.",
            },
            {
                "label": "Change password",
                "url": reverse("accounts:password_change"),
                "description": "Keep your account secure.",
            },
        ],
    )


@role_required(Role.STUDENT)
def student_dashboard(request):
    return _render_dashboard(
        request,
        "Student Dashboard",
        "Your learning workspace. Academic modules are added in later phases.",
        [
            {
                "label": "My profile",
                "url": reverse("accounts:profile"),
                "description": "Update contact details and profile image.",
            },
            {
                "label": "Change password",
                "url": reverse("accounts:password_change"),
                "description": "Keep your account secure.",
            },
        ],
    )


# ---------------------------------------------------------------------------
# Account management (Super Admin / Institute Admin)
# ---------------------------------------------------------------------------
def _scoped_users(user):
    """Return only the accounts the requesting manager is allowed to see."""
    queryset = User.objects.select_related("institute")
    if user.role == Role.SUPER_ADMIN:
        return queryset.filter(is_superuser=False)
    return queryset.filter(
        institute=user.institute, role__in=[Role.TEACHER, Role.STUDENT]
    )


@super_admin_required
def institute_create(request):
    if request.method == "POST":
        form = InstituteForm(request.POST)
        if form.is_valid():
            institute = form.save()
            messages.success(request, f"Institute '{institute.name}' created.")
            return redirect("accounts:institute_admin_create")
    else:
        form = InstituteForm()
    return render(
        request,
        "accounts/institute_form.html",
        {"form": form, "form_title": "Create Institute"},
    )


@super_admin_required
def institute_admin_create(request):
    if request.method == "POST":
        form = InstituteAdminCreateForm(request.POST)
        if form.is_valid():
            admin_user = form.save()
            messages.success(
                request, f"Institute admin '{admin_user.email}' created."
            )
            return redirect("accounts:user_list")
    else:
        form = InstituteAdminCreateForm()
    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "form_title": "Create Institute Admin",
            "form_description": "Only Super Admins can create institute administrators.",
        },
    )


@institute_admin_required
def role_user_create(request):
    if request.user.institute is None:
        messages.error(request, "Your account is not linked to an institute.")
        return redirect(dashboard_url_for(request.user))

    if request.method == "POST":
        form = RoleUserCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save(commit=False)
            new_user.institute = request.user.institute
            new_user.save()
            messages.success(request, f"Account '{new_user.email}' created.")
            return redirect("accounts:user_list")
    else:
        form = RoleUserCreateForm()
    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "form_title": "Create Teacher or Student",
            "form_description": "Accounts are created inside your own institute only.",
        },
    )


@management_required
def user_list(request):
    users = _scoped_users(request.user)
    role_filter = request.GET.get("role", "")
    search_query = request.GET.get("q", "").strip()

    if role_filter in dict(Role.choices):
        users = users.filter(role=role_filter)
    if search_query:
        scoped = _scoped_users(request.user)
        users = (
            scoped.filter(email__icontains=search_query)
            | scoped.filter(first_name__icontains=search_query)
            | scoped.filter(last_name__icontains=search_query)
        ).distinct()

    return render(
        request,
        "accounts/user_list.html",
        {
            "users": users,
            "role_choices": Role.choices,
            "role_filter": role_filter,
            "search_query": search_query,
        },
    )


@require_POST
@management_required
def set_user_active(request, pk, active):
    """Activate or deactivate an account within the manager's scope."""
    target = get_object_or_404(_scoped_users(request.user), pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "You cannot change your own account status.")
        return redirect("accounts:user_list")

    target.is_active = active
    target.save(update_fields=["is_active"])
    state = "activated" if active else "deactivated"
    messages.success(request, f"Account '{target.email}' {state}.")
    return redirect("accounts:user_list")


# ---------------------------------------------------------------------------
# Invitation-based registration
# ---------------------------------------------------------------------------
def _send_invitation_email(request, invitation):
    register_url = request.build_absolute_uri(
        reverse("accounts:invitation_register", args=[str(invitation.token)])
    )
    context = {
        "invitation": invitation,
        "register_url": register_url,
        "role_label": invitation.get_role_display(),
    }
    subject = render_to_string(
        "accounts/email/invitation_subject.txt", context
    ).strip()
    body = render_to_string("accounts/email/invitation_email.txt", context)
    send_mail(subject, body, None, [invitation.email], fail_silently=False)


@institute_admin_required
def invitation_create(request):
    if request.user.institute is None:
        messages.error(request, "Your account is not linked to an institute.")
        return redirect(dashboard_url_for(request.user))

    if request.method == "POST":
        form = InvitationForm(request.POST)
        if form.is_valid():
            invitation = form.save(commit=False)
            invitation.institute = request.user.institute
            invitation.created_by = request.user
            invitation.save()
            _send_invitation_email(request, invitation)
            messages.success(request, f"Invitation sent to {invitation.email}.")
            return redirect("accounts:user_list")
    else:
        form = InvitationForm()

    return render(
        request,
        "accounts/invitation_form.html",
        {"form": form, "form_title": "Invite Teacher or Student"},
    )


def invitation_register(request, token):
    """Complete an approved invitation. There is no public self-registration."""
    invitation = get_object_or_404(Invitation, token=token)

    if not invitation.is_valid:
        return render(
            request,
            "accounts/invitation_invalid.html",
            {"invitation": invitation},
            status=400,
        )

    if User.objects.filter(email__iexact=invitation.email).exists():
        return render(
            request,
            "accounts/invitation_invalid.html",
            {"invitation": invitation},
            status=400,
        )

    if request.method == "POST":
        form = InvitationRegisterForm(request.POST)
        form.invitation_email = invitation.email
        if form.is_valid():
            from django.db import transaction

            try:
                with transaction.atomic():
                    # Lock the invitation so concurrent submissions cannot both
                    # consume the same single-use token.
                    locked = Invitation.objects.select_for_update().get(pk=invitation.pk)
                    if not locked.is_valid:
                        raise Invitation.DoesNotExist()
                    if User.objects.filter(email__iexact=locked.email).exists():
                        raise ValidationError("An account with this email already exists.")
                    new_user = User.objects.create_user(
                        email=locked.email,
                        password=form.cleaned_data["password1"],
                        first_name=form.cleaned_data["first_name"],
                        last_name=form.cleaned_data["last_name"],
                        role=locked.role,
                        institute=locked.institute,
                    )
                    locked.accept(new_user)
            except (Invitation.DoesNotExist, ValidationError):
                return render(
                    request,
                    "accounts/invitation_invalid.html",
                    {"invitation": invitation},
                    status=400,
                )
            messages.success(
                request, "Your account is ready. Please sign in to continue."
            )
            return redirect("accounts:login")
    else:
        form = InvitationRegisterForm()
        form.invitation_email = invitation.email

    return render(
        request,
        "accounts/invitation_register.html",
        {"form": form, "invitation": invitation},
    )
