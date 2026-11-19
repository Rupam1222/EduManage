"""Settings used for local development.

Selected by default in ``manage.py``. Override any value via the ``.env`` file.
"""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = True
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"]
)

# SQLite is the development default. Set DATABASE_URL in .env to use another
# engine locally, for example: mysql://user:pass@127.0.0.1:3306/edumanage_dev
if env.str("DATABASE_URL", default=""):
    DATABASES["default"] = env.db_url("DATABASE_URL")

# Never send real email while developing.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Verbose console output during development without flooding the shell with
# every SQL statement. Flip ``django.db.backends`` to DEBUG to inspect queries.
LOGGING["handlers"]["console"]["level"] = "DEBUG"
LOGGING["loggers"]["edumanage"]["level"] = "DEBUG"
LOGGING["loggers"]["django.db.backends"] = {
    "handlers": ["console"],
    "level": "WARNING",
    "propagate": False,
}
