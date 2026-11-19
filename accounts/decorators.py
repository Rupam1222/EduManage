"""Role-based view decorators.

Every protected view checks both authentication and role. A user who is logged
in with the wrong role receives HTTP 403 instead of another role's dashboard.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Role


def role_required(*roles):
    """Allow only users whose role is in ``roles``."""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied(
                    "You do not have permission to access this area."
                )
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


super_admin_required = role_required(Role.SUPER_ADMIN)
institute_admin_required = role_required(Role.INSTITUTE_ADMIN)
teacher_required = role_required(Role.TEACHER)
student_required = role_required(Role.STUDENT)
management_required = role_required(Role.SUPER_ADMIN, Role.INSTITUTE_ADMIN)
