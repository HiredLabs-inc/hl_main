from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from userprofile.va_api import confirm_veteran_status


class Command(BaseCommand):
    def handle(self, *args, **options):
        User = settings.AUTH_USER_MODEL.objects.first()
        print(confirm_veteran_status(user))
