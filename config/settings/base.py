"""
Base settings shared by development and production.

All deployment-specific values come from environment variables (optionally
loaded from a `.env` file in the project root) so the same codebase runs on
PythonAnywhere with SQLite today and on any host with PostgreSQL later.
"""
from pathlib import Path
import os

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_dotenv(path):
    """Minimal .env loader: KEY=VALUE lines, '#' comments, no interpolation."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


SECRET_KEY = env("SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Project apps
    "core",
    "accounts",
    "profiles",
    "exercises",
    "programs",
    "workouts",
    "progress",
    "nutrition",
    "supplements",
    "coaching",
    "imports",
    "calendar_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.ForcePasswordChangeMiddleware",
]

ROOT_URLCONF = "config.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database: PostgreSQL when DATABASE_URL is set, SQLite otherwise.
_database_url = env("DATABASE_URL")
if _database_url:
    DATABASES = {"default": dj_database_url.parse(_database_url, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.EmailOrUsernameBackend"]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "America/Chicago")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Public media (nothing private is ever placed here).
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Private uploads live outside MEDIA_ROOT and are only reachable through
# authenticated download views (see core.services.storage / imports.views).
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", BASE_DIR / "private_media"))
MEDIA_STORAGE_BACKEND = env("MEDIA_STORAGE_BACKEND", "local")  # future: "s3"

# Upload limits (MB)
MAX_EXCEL_UPLOAD_MB = env_int("MAX_EXCEL_UPLOAD_MB", 5)
MAX_PDF_UPLOAD_MB = env_int("MAX_PDF_UPLOAD_MB", 10)
MAX_IMAGE_UPLOAD_MB = env_int("MAX_IMAGE_UPLOAD_MB", 5)
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Simple in-database rate limiting knobs (see core.services.ratelimit).
LOGIN_RATE_LIMIT_ATTEMPTS = env_int("LOGIN_RATE_LIMIT_ATTEMPTS", 8)
LOGIN_RATE_LIMIT_WINDOW_MINUTES = env_int("LOGIN_RATE_LIMIT_WINDOW_MINUTES", 10)
UPLOAD_RATE_LIMIT_PER_HOUR = env_int("UPLOAD_RATE_LIMIT_PER_HOUR", 20)

# Displayed default estimated-1RM formula: "epley" or "brzycki".
DEFAULT_E1RM_FORMULA = env("DEFAULT_E1RM_FORMULA", "epley")

# Google Calendar integration stays disabled until OAuth credentials exist.
GOOGLE_CALENDAR_ENABLED = env_bool("GOOGLE_CALENDAR_ENABLED", False)
GOOGLE_CALENDAR_CLIENT_ID = env("GOOGLE_CALENDAR_CLIENT_ID", "")
GOOGLE_CALENDAR_CLIENT_SECRET = env("GOOGLE_CALENDAR_CLIENT_SECRET", "")
GOOGLE_CALENDAR_REDIRECT_URI = env("GOOGLE_CALENDAR_REDIRECT_URI", "")
GOOGLE_TOKEN_ENCRYPTION_KEY = env("GOOGLE_TOKEN_ENCRYPTION_KEY", "")
SITE_URL = env("SITE_URL", "")
