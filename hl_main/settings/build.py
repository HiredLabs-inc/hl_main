"""
Settings used only for `collectstatic` during `docker build`.

Needs no secrets, credentials or database, so no key file has to be baked into
the image. Static settings must match cloud.py.
"""
import os

from .base import *

SECRET_KEY = "build-only-not-secret"
STATIC_ROOT = os.path.join(BASE_DIR, "main_static/")
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}
