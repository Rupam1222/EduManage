"""Settings used in production.

Activate with ``DJANGO_SETTINGS_MODULE=CoachingApp.settings.production``.

Required environment variables:
    SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL,
    RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET

Strongly recommended:
    CSRF_TRUSTED_ORIGINS, DEFAULT_FROM_EMAIL, EMAIL_HOST,
    EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, ADMIN_EMAIL

The checks registered by :mod:`CoachingApp.checks` verify this configuration
when ``python manage.py check --deploy`` is run.
"""

from .base import *  # noqa: F401,F403
from .base import env

# Importing this module registers the production deployment checks.
from .. import checks as _production_checks  # noqa: F401

# PyMySQL is the portable, pure-Python MySQL driver used by this project.
# If mysqlclient (native MySQLdb) is installed instead, it is used as-is.
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # pragma: no cover - depends on the chosen driver
    pass

DEBUG = False

# Fail fast if the deployment is not configured properly.
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Production uses MySQL (e.g. mysql://user:pass@db:3306/edumanage).
DATABASES["default"] = env.db_url("DATABASE_URL")

# Optional TLS for the database connection (recommended for remote MySQL).
DATABASE_SSL_CA = env("DATABASE_SSL_CA", default="")
if DATABASE_SSL_CA:
    DATABASES["default"].setdefault("OPTIONS", {})["ssl"] = {"ca": DATABASE_SSL_CA}

# Optional cookie domains, useful when the app and API share a parent domain.
SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN", default=None) or None
CSRF_COOKIE_DOMAIN = env("CSRF_COOKIE_DOMAIN", default=None) or None

# HTTPS / cookie hardening. SECURE_SSL_REDIRECT=False is only acceptable when
# TLS is terminated by an upstream proxy that already enforces HTTPS.
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
# Trust X-Forwarded-Proto only behind a proxy that OVERWRITES this header.
TRUST_X_FORWARDED_PROTO = env.bool("TRUST_X_FORWARDED_PROTO", default=True)
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https") if TRUST_X_FORWARDED_PROTO else None
)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Static files are collected with ``collectstatic`` and served by the web
# server / CDN. Media files are NEVER served by Django here: all uploads are
# read through authenticated views. See DEPLOYMENT.md for the web-server rules.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
)

# Live payment credentials are mandatory in production. The sandbox flag
# defaults to False so a test key cannot silently enable test-mode checkout.
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET")
RAZORPAY_SANDBOX = env.bool("RAZORPAY_SANDBOX", default=False)

# Production logging: keep the application log useful without flooding the
# console. 4xx/5xx always go to errors.log (and to ADMINS when configured).
LOGGING["handlers"]["console"]["level"] = "WARNING"
LOGGING["loggers"]["django"]["level"] = "WARNING"
LOGGING["loggers"]["edumanage"]["level"] = "INFO"
