from django.conf import settings
from django.core.management import BaseCommand

from cold_apply.text_generation import generate_text


class Command(BaseCommand):
    help = "Smoke test for resume text generation: one call to settings.GEMINI_MODEL."

    def handle(self, *args, **options):
        self.stdout.write(f"{settings.GEMINI_MODEL} in {settings.GCP_PROJECT_ID}/{settings.GEMINI_LOCATION}")
        self.stdout.write(generate_text("Write one resume bullet point for a software engineer."))
