"""Production settings: hardened cookies, HTTPS-aware, WhiteNoise manifest static."""
from .base import *  # noqa: F401,F403
from .base import env, env_bool

DEBUG = env_bool("DEBUG", False)

if env("SECRET_KEY") is None:
    raise RuntimeError("SECRET_KEY environment variable is required in production.")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# PythonAnywhere terminates TLS at the load balancer.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Free PythonAnywhere accounts serve HTTPS but the WSGI app sees HTTP, so
# redirect is optional; enable via env on hosts with proper forwarding.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "0"))

EMAIL_BACKEND = env(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@localhost")

# Never leak raw tracebacks; log to file that stays on the server.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"}},
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "django-error.log",  # noqa: F405
            "maxBytes": 1_000_000,
            "backupCount": 2,
            "formatter": "simple",
        },
    },
    "loggers": {
        "django": {"handlers": ["file"], "level": "WARNING", "propagate": True},
    },
}
