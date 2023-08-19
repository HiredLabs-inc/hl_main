from django.core.management import BaseCommand


class Command(BaseCommand):
    help = "Load development data into the database"

    def handle(self, *args, **options):
        from cold_apply.models import Applicant, Participant
        from resume.models import Education, Experience, Overview

        # Create Participants

        # Create Jobs

        # Create Skills
