from .base import *

SECRET_KEY = "doesntmatterdfklmasdlkfmsdaf"
STATIC_ROOT = os.path.join(BASE_DIR, "static_files/")
# MEDIA_ROOT = os.path.join(BASE_DIR, "media/")
MEDIA_URL = "media/"
DEBUG = True

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

GS_BUCKET_NAME = f"{os.environ['GCP_PROJECT_ID']}-{os.environ['GCP_BUCKET_SUFFIX']}"

STATIC_URL = "/static/"
DEFAULT_FILE_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
STATICFILES_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
GS_DEFAULT_ACL = "publicRead"