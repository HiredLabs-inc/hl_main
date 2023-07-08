from .base import *

SECRET_KEY = "doesntmatterdfklmasdlkfmsdaf"
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]

# MEDIA_ROOT = os.path.join(BASE_DIR, "media/")
MEDIA_URL = "media/"
DEBUG = True

INSTALLED_APPS += [
    "debug_toolbar",
    "django_extensions",
]
INTERNAL_IPS = ["127.0.0.1"]
MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "postgres",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "db",
    }
}

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static_files/")

MEDIA_ROOT = os.path.join(BASE_DIR, "tmp/")

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
