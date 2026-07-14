"""Sample PythonAnywhere WSGI configuration.

On PythonAnywhere: Web tab → your app → "WSGI configuration file", replace the
contents with this file (adjust USERNAME and the project path).
The .env file in the project root supplies SECRET_KEY etc.
"""
import os
import sys

PROJECT_PATH = "/home/USERNAME/pt-app"   # <-- adjust

if PROJECT_PATH not in sys.path:
    sys.path.insert(0, PROJECT_PATH)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.prod"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
