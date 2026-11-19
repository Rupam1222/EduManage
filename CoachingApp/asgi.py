"""ASGI config for the EduManage SaaS project.

It exposes the ASGI callable as a module-level variable named ``application``.

Defaults to production settings so a deployment can never silently run with
DEBUG=True. Local `manage.py` commands still default to development settings.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "CoachingApp.settings.production"
)

application = get_asgi_application()
