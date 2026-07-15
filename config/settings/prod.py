"""Production settings: hardened cookies, HTTPS-aware, WhiteNoise manifest static."""
from .base import *  # noqa: F401,F403
from .base import env, env_bool

if env_bool("DEBUG", False):
    raise RuntimeError("DEBUG must remain False in production.")
DEBUG = False

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
# PythonAnywhere forwards the original scheme, so HTTPS enforcement is safe.
# Other hosts may explicitly override these only when their proxy performs the
# equivalent redirect/HSTS policy itself.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", True)

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
