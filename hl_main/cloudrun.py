"""Cloud Run runtime details used by settings/cloud.py.

Cloud Run serves each service at two URLs: the legacy hashed one
(<service>-<hash>-<region code>.a.run.app) and the deterministic one
(<service>-<project number>.<region>.run.app). The legacy URL comes from the
CLOUDRUN_*_URL entries in the app secret; the deterministic host is derived
here from the running service's name and the project number from the metadata
server, so both URLs work without editing the secret.
"""
import logging
import os
import urllib.request

logger = logging.getLogger(__name__)

METADATA_URL = "http://metadata.google.internal/computeMetadata/v1/project/numeric-project-id"


def _project_number():
    request = urllib.request.Request(METADATA_URL, headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(request, timeout=2) as response:
        return response.read().decode().strip()


def deterministic_host(region):
    """Host of this service's deterministic URL, or None outside a Cloud Run service.

    K_SERVICE is set by Cloud Run services only (not jobs, which serve no requests).
    """
    service = os.environ.get("K_SERVICE")
    if not service or not region:
        return None
    try:
        number = _project_number()
    except OSError:
        logger.warning("Could not read the project number from the metadata server", exc_info=True)
        return None
    return f"{service}-{number}.{region}.run.app"
