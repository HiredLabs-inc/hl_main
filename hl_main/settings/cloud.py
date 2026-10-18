"""
Settings for every Cloud Run environment (stage, prod).

Environment differences come only from environment variables: the Cloud Run
service sets GCP_PROJECT_ID and GCP_SECRETS_NAME, and the rest is read from the
.env-formatted Secret Manager secret named by GCP_SECRETS_NAME.
"""
import os
from io import StringIO
from urllib.parse import urlparse

from google.cloud import secretmanager

from hl_main.cloudrun import deterministic_host

from .base import *

PRODUCTION = True
DEBUG = False

# Load the .env blob from Secret Manager into os.environ (existing values win).
GCP_PROJECT_ID = env("GCP_PROJECT_ID")
GCP_SECRETS_NAME = env("GCP_SECRETS_NAME")
_client = secretmanager.SecretManagerServiceClient()
_name = f"projects/{GCP_PROJECT_ID}/secrets/{GCP_SECRETS_NAME}/versions/latest"
env.read_env(StringIO(_client.access_secret_version(name=_name).payload.data.decode("UTF-8")))

SECRET_KEY = env("DJANGO_SECRET_KEY")
VA_API_KEY = env("VA_API_KEY")
SITE_ID = env.int("SITE_ID", default=1)
TURNSTILE_SITE_KEY = env("TURNSTILE_SITE_KEY")
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY")

# Hosts: custom domains (comma-separated) plus both Cloud Run URLs (see hl_main/cloudrun.py).
ALLOWED_HOSTS = [h for h in env.list("ALLOWED_HOSTS", default=["www.hiredlabs.org", "hiredlabs.org"]) if h]
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]
CLOUDRUN_SERVICE_URL = env("CLOUDRUN_SERVICE_URL", default="")
CLOUDRUN_WORKER_URL = env("CLOUDRUN_WORKER_URL", default="")
for _url in (CLOUDRUN_SERVICE_URL, CLOUDRUN_WORKER_URL):
    if _url:
        ALLOWED_HOSTS.append(urlparse(_url).netloc)
        CSRF_TRUSTED_ORIGINS.append(_url.rstrip("/"))
GCP_REGION = env("GCP_REGION")
_host = deterministic_host(GCP_REGION)
if _host and _host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_host)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_host}")

# Background tasks (see background_tasks/queue.py)
GCP_TASK_QUEUE = env("GCP_TASK_QUEUE")
GCP_SERVICE_ACCOUNT = env("GCP_SERVICE_ACCOUNT")

# Database: private IP over Direct VPC egress / Serverless VPC connector.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("GCP_CLOUDSQL_DB_NAME"),
        "HOST": env("GCP_CLOUDSQL_PRIVATE_IP"),
        "USER": env("GCP_CLOUDSQL_USER"),
        "PASSWORD": env("GCP_CLOUDSQL_PASSWORD"),
        "PORT": 5432,
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "main_cache",
    }
}

# Media in GCS (credentials from the runtime service account), static via whitenoise.
GS_BUCKET_NAME = env("GS_BUCKET_NAME")
GS_FILE_OVERWRITE = False
MEDIA_URL = "media/"
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "main_static/")
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "default": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
    },
}

# HSTS for a year. Not preloaded yet: preload is hard to undo once browsers ship it.
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Links in emails (confirmation, password reset) use https.
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

# google cloud run proxy sends http to containers
# so need django to recognise HTTP_X_FORWARDED_PROTO header
# to stop a redirect loop
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

DEFAULT_FROM_EMAIL = "The HiredLabs Team <info@hiredlabs.org>"
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Sends email to SMTP server
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default=None)
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default=None)
