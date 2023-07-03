from .base import *

SECRET_KEY = "doesntmatterdfklmasdlkfmsdaf"

# MEDIA_ROOT = os.path.join(BASE_DIR, "media/")
MEDIA_URL = "media/"
DEBUG = False

INSTALLED_APPS.append("debug_toolbar")
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
