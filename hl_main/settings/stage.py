# Kept so existing DJANGO_SETTINGS_MODULE=hl_main.settings.stage deployments keep working.
# The legacy stage database uses django.contrib.sites id 2.
import os

os.environ.setdefault("SITE_ID", "2")

from .cloud import *
