"""Template context processors shared across the project."""

from django.conf import settings
from django.utils import timezone


def project_context(request):
    """Expose common project metadata to every template."""
    return {
        "project_name": getattr(
            settings, "PROJECT_NAME", "EduManage SaaS"
        ),
        "project_description": getattr(
            settings, "PROJECT_DESCRIPTION", "Coaching Institute Management"
        ),
        "current_year": timezone.now().year,
    }
