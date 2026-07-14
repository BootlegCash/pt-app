"""Development settings: DEBUG on, relaxed static storage, console email."""
from .base import *  # noqa: F401,F403
from .base import env_bool

DEBUG = env_bool("DEBUG", True)

STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
