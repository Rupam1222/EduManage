"""Shared settings for the EduManage SaaS project.

This module contains configuration that is common to every environment.
Environment specific overrides live in :mod:`~CoachingApp.settings.development`
and :mod:`~CoachingApp.settings.production`.
"""

from pathlib import Path

import environ

# ``base.py`` lives in CoachingApp/settings/, so three parents reach the repo root.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read the optional .env file once, at settings import time.
env = environ.Env(DEBUG=(bool, False))
_env_file = BASE_DIR / ".env"
if _env_file.is_file():
    environ.Env.read_env(str(_env_file))

# ---------------------------------------------------------------------------
# Project metadata
# ---------------------------------------------------------------------------
PROJECT_NAME = "EduManage SaaS"
PROJECT_DESCRIPTION = "Coaching Institute Management Platform"

# ---------------------------------------------------------------------------
# Security / core
# ---------------------------------------------------------------------------
# The default is intentionally unsafe: production must supply SECRET_KEY.
SECRET_KEY = env(
    "SECRET_KEY", default="django-insecure-development-only-change-me"
)
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

LOCAL_APPS = [
    "core.apps.CoreConfig",
    "accounts.apps.AccountsConfig",
    "superadmin.apps.SuperadminConfig",
    "institutes.apps.InstitutesConfig",
    "subscriptions.apps.SubscriptionsConfig",
    "payments.apps.PaymentsConfig",
    "licenses.apps.LicensesConfig",
    "students.apps.StudentsConfig",
    "teachers.apps.TeachersConfig",
    "courses.apps.CoursesConfig",
    "batches.apps.BatchesConfig",
    "study_material.apps.StudyMaterialConfig",
    "attendance.apps.AttendanceConfig",
    "assignments.apps.AssignmentsConfig",
    "examinations.apps.ExaminationsConfig",
    "fees.apps.FeesConfig",
    "notifications.apps.NotificationsConfig",
    "reports.apps.ReportsConfig",
    "activity_logs.apps.ActivityLogsConfig",
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # Must run after AuthenticationMiddleware (needs request.user) and after
    # MessageMiddleware (pending institutes receive a warning message).
    "core.middleware.TenantIsolationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "CoachingApp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.project_context",
                "notifications.context_processors.notification_badge",
            ],
        },
    },
]

WSGI_APPLICATION = "CoachingApp.wsgi.application"
ASGI_APPLICATION = "CoachingApp.asgi.application"

# ---------------------------------------------------------------------------
# Database (development default; production overrides with MySQL via DATABASE_URL)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}

# ---------------------------------------------------------------------------
# Authentication and authorization
# ---------------------------------------------------------------------------
# The custom user model is declared before the first migration. It uses email
# as USERNAME_FIELD and is managed by accounts.backends.EmailBackend.
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = ["accounts.backends.EmailBackend"]

# Django's PBKDF2 hasher (strong by default). Only built-in hashers are
# listed so no optional C/Argon2 library is required for a fresh install.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# Secure session defaults. Cookies are further hardened in production.py.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 60 * 60  # 8 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static and media files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
# Override STATIC_ROOT/STATIC_BUCKET when the deployment keeps collected assets
# on a separate volume or CDN. collectstatic always writes to STATIC_ROOT.
STATIC_ROOT = Path(env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles")))
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
# Keep uploads outside the web root in production. The path is configurable so
# a host can mount a durable volume (see DEPLOYMENT.md). Django serves media
# only in development; production access always goes through authenticated
# views that re-check tenant, role and batch membership.
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# Global upload caps (defence in depth against disk-exhaustion DoS). Individual
# modules apply stricter, field-specific limits on top of these.
DATA_UPLOAD_MAX_MEMORY_SIZE = 26 * 1024 * 1024  # 26 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 26 * 1024 * 1024

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=30)
EMAIL_SUBJECT_PREFIX = "[EduManage] "
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL", default="no-reply@edumanage.local"
)
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# When ADMIN_EMAIL is set, 500 errors are also mailed to the operations team.
ADMIN_EMAIL = env("ADMIN_EMAIL", default="")
ADMINS = (("EduManage Operations", ADMIN_EMAIL),) if ADMIN_EMAIL else ()
MANAGERS = ADMINS

# ---------------------------------------------------------------------------
# Razorpay payments
# ---------------------------------------------------------------------------
# Credentials come from the environment only; never commit real keys. Test
# keys (rzp_test_...) and sandbox mode are used by default in development.
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="")
RAZORPAY_SANDBOX = env.bool("RAZORPAY_SANDBOX", default=True)
RAZORPAY_CURRENCY = env("RAZORPAY_CURRENCY", default="INR")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = Path(env("LOG_DIR", default=str(BASE_DIR / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "simple",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "verbose",
            "filename": str(LOG_DIR / "django.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        },
        "errors_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "verbose",
            "filename": str(LOG_DIR / "errors.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "errors_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "edumanage": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
}

# Error logging: rotating files always capture 5xx/4xx request errors. When an
# operations address is configured they are also emailed via Django's
# AdminEmailHandler (uses ADMINS/SERVER_EMAIL above).
if ADMIN_EMAIL:
    LOGGING["handlers"]["mail_admins"] = {
        "class": "django.utils.log.AdminEmailHandler",
        "level": "ERROR",
    }
    LOGGING["loggers"]["django.request"]["handlers"].append("mail_admins")
