"""Deployment-specific Django system checks.

Imported by :mod:`CoachingApp.settings.production`, so these checks only run
when the production settings module is active. Run them with::

    python manage.py check --deploy --settings=CoachingApp.settings.production
"""

import os
from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register

INSECURE_SECRET = "django-insecure-development-only-change-me"
IN_MEMORY_EMAIL_BACKENDS = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
}


@register(Tags.security, deploy=True)
def check_production_secret_key(app_configs, **kwargs):
    errors = []
    secret = settings.SECRET_KEY or ""
    if secret == INSECURE_SECRET or len(secret) < 50:
        errors.append(
            Error(
                "SECRET_KEY must be a unique random value of at least 50 "
                "characters in production.",
                hint="Generate one with: python -c \"from django.core.management "
                "utils import get_random_secret_key; print(get_random_secret_key())\"",
                id="edumanage.E001",
            )
        )
    return errors


@register(Tags.security, deploy=True)
def check_production_debug_and_hosts(app_configs, **kwargs):
    errors = []
    if settings.DEBUG:
        errors.append(
            Error("DEBUG must be False in production.", id="edumanage.E002")
        )
    hosts = list(settings.ALLOWED_HOSTS)
    if not hosts or "*" in hosts:
        errors.append(
            Error(
                "ALLOWED_HOSTS must be a specific list of hostnames; wildcards "
                "are not allowed.",
                hint="Example: ALLOWED_HOSTS=app.example.com,www.example.com",
                id="edumanage.E003",
            )
        )
    return errors


@register(Tags.security, deploy=True)
def check_production_database(app_configs, **kwargs):
    # Local/CI checks often have no MySQL server available. Set this flag only
    # for those checks; production must never set it.
    if os.environ.get("EDUMANAGE_SKIP_DB_ENGINE_CHECK") == "1":
        return [
            Warning(
                "Database engine check skipped (EDUMANAGE_SKIP_DB_ENGINE_CHECK=1). "
                "The production host must use MySQL.",
                id="edumanage.W005",
            )
        ]
    engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
    if "mysql" not in engine:
        return [
            Error(
                "Production must use a MySQL database.",
                hint="Set DATABASE_URL=mysql://user:password@host:3306/edumanage",
                id="edumanage.E004",
            )
        ]
    return []


@register(Tags.security, deploy=True)
def check_production_email(app_configs, **kwargs):
    if settings.EMAIL_BACKEND in IN_MEMORY_EMAIL_BACKENDS:
        return [
            Error(
                "Production email must use a real SMTP backend; subscription "
                "reminders and password resets would otherwise be lost.",
                hint="Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend "
                "and configure EMAIL_HOST/EMAIL_HOST_USER/EMAIL_HOST_PASSWORD.",
                id="edumanage.E005",
            )
        ]
    return []


@register(Tags.security, deploy=True)
def check_production_payment_credentials(app_configs, **kwargs):
    errors = []
    key_id = settings.RAZORPAY_KEY_ID or ""
    key_secret = settings.RAZORPAY_KEY_SECRET or ""
    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET or ""

    if not key_id or not key_secret:
        errors.append(
            Error(
                "Razorpay key ID and secret are required in production.",
                id="edumanage.E006",
            )
        )
    if settings.RAZORPAY_SANDBOX or key_id.startswith("rzp_test_"):
        errors.append(
            Error(
                "Razorpay sandbox mode is enabled in production.",
                hint="Use live rzp_live_... keys and set RAZORPAY_SANDBOX=False.",
                id="edumanage.E007",
            )
        )
    if not webhook_secret:
        errors.append(
            Error(
                "RAZORPAY_WEBHOOK_SECRET is required in production.",
                hint="Use the distinct webhook signing secret from the Razorpay "
                "dashboard; do not rely on the key-secret fallback.",
                id="edumanage.E008",
            )
        )
    elif webhook_secret == key_secret:
        errors.append(
            Error(
                "RAZORPAY_WEBHOOK_SECRET must differ from RAZORPAY_KEY_SECRET.",
                id="edumanage.E009",
            )
        )
    return errors


@register(Tags.security, deploy=True)
def check_production_cookie_hardening(app_configs, **kwargs):
    errors = []
    if not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE:
        errors.append(
            Error(
                "Session and CSRF cookies must carry the Secure flag in production.",
                id="edumanage.E010",
            )
        )
    if not settings.SECURE_SSL_REDIRECT:
        errors.append(
            Error(
                "SECURE_SSL_REDIRECT must be True unless TLS is enforced by a "
                "trusted upstream proxy.",
                id="edumanage.E011",
            )
        )
    return errors


@register(Tags.security, deploy=True)
def check_production_hardening_warnings(app_configs, **kwargs):
    warnings = []
    media_root = Path(settings.MEDIA_ROOT).resolve()
    base_dir = Path(settings.BASE_DIR).resolve()
    if media_root == base_dir or base_dir in media_root.parents:
        warnings.append(
            Warning(
                "MEDIA_ROOT is inside the application directory.",
                hint="Mount uploads outside the web root and deny /media/ in "
                "the web-server configuration (see DEPLOYMENT.md).",
                id="edumanage.W001",
            )
        )
    if not settings.CSRF_TRUSTED_ORIGINS:
        warnings.append(
            Warning(
                "CSRF_TRUSTED_ORIGINS is empty.",
                hint="Set it to https://<your-domain> so CSRF works reliably "
                "behind proxies and CDNs.",
                id="edumanage.W002",
            )
        )
    if not settings.ADMINS:
        warnings.append(
            Warning(
                "ADMIN_EMAIL is not configured; server errors will not be emailed.",
                hint="Set ADMIN_EMAIL=ops@example.com.",
                id="edumanage.W003",
            )
        )
    if settings.SECURE_HSTS_SECONDS < 31536000:
        warnings.append(
            Warning(
                "SECURE_HSTS_SECONDS is shorter than the recommended year.",
                id="edumanage.W004",
            )
        )
    return warnings
