"""Role-based class-based-view mixins."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .models import Role


class RoleRequiredMixin(LoginRequiredMixin):
    """Require authentication and one of ``allowed_roles``."""

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in self.allowed_roles:
            raise PermissionDenied("You do not have permission to access this area.")
        return super().dispatch(request, *args, **kwargs)


class SuperAdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = (Role.SUPER_ADMIN,)


class InstituteAdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = (Role.INSTITUTE_ADMIN,)


class TeacherRequiredMixin(RoleRequiredMixin):
    allowed_roles = (Role.TEACHER,)


class StudentRequiredMixin(RoleRequiredMixin):
    allowed_roles = (Role.STUDENT,)


class ManagementRequiredMixin(RoleRequiredMixin):
    allowed_roles = (Role.SUPER_ADMIN, Role.INSTITUTE_ADMIN)
