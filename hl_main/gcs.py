"""Google Cloud Storage helpers that use Application Default Credentials.

On Cloud Run the credentials come from the metadata server (no key file). Signed
URLs are then signed through the IAM signBlob API, which requires the runtime
service account to hold roles/iam.serviceAccountTokenCreator on itself
(granted in infra/terraform).
"""
import datetime

import google.auth
from google.auth import compute_engine
from google.auth.transport.requests import Request
from google.cloud import storage

_credentials = None


def _get_credentials():
    global _credentials
    if _credentials is None:
        _credentials, _ = google.auth.default()
    if not _credentials.valid:
        _credentials.refresh(Request())
    return _credentials


def generate_signed_url(bucket_name, object_name, expiration=604_800, http_method="GET"):
    """Return a V4 signed URL for an object. Expiration is in seconds (max 7 days)."""
    credentials = _get_credentials()
    blob = storage.Client(credentials=credentials).bucket(bucket_name).blob(object_name)
    signing_kwargs = {}
    if isinstance(credentials, compute_engine.Credentials):
        # No private key available: sign remotely via IAM.
        signing_kwargs = {
            "service_account_email": credentials.service_account_email,
            "access_token": credentials.token,
        }
    return blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(seconds=expiration),
        method=http_method,
        **signing_kwargs,
    )


def upload_file(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client(credentials=_get_credentials())
    blob = storage_client.bucket(bucket_name).blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    return blob.public_url
