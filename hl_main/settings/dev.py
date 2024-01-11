from .base import *

SECRET_KEY = "doesntmatterdfklmasdlkfmsdaf"
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
VA_API_KEY = os.environ.get("VA_API_KEY")

# MEDIA_ROOT = os.path.join(BASE_DIR, "media/")
# MEDIA_URL = "media/"
DEBUG = True

INSTALLED_APPS += ["debug_toolbar", "django_extensions", "django_browser_reload"]
INTERNAL_IPS = ["127.0.0.1"]
MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]


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
STATIC_ROOT = os.path.join(BASE_DIR, "static/")

# MEDIA_ROOT = os.path.join(BASE_DIR, "tmp/")

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
ACCOUNT_LOGIN_ATTEMPTS = None

# Writes to stdout instead of sending; only for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
#
# EMAIL_HOST = "smtp.gmail.com"
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# DEFAULT_FROM_EMAIL = "info@hiredlabs.org"
# EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
# EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")

# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.dummy.DummyCache",
#     }
# }

# del TEMPLATES[0]["APP_DIRS"]
# TEMPLATES[0]["OPTIONS"]["loaders"] = [
#     "django.template.loaders.filesystem.Loader",
#     "django.template.loaders.app_directories.Loader",
# ]



