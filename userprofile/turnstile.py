"""Cloudflare Turnstile server-side check, see
https://developers.cloudflare.com/turnstile/get-started/server-side-validation/"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
# Name of the POST field the Turnstile widget adds to the form.
RESPONSE_FIELD = "cf-turnstile-response"


def verify(token, remote_ip=None):
    """True if Cloudflare accepts the widget's token. Fails closed on network errors."""
    if not token:
        return False
    data = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        response = requests.post(VERIFY_URL, data=data, timeout=5)
        return response.json().get("success") is True
    except (requests.RequestException, ValueError):
        logger.warning("Turnstile verification failed", exc_info=True)
        return False
