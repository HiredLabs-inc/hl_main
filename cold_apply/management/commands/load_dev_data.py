from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from cold_apply.models import Participant, Skill
from cold_apply.tests.factories import (
    JobFactory,
    ParticipantFactory,
    SkillFactory,
    UserFactory,
)
from resume.models import Organization, Position
from userprofile.models import Profile

User = get_user_model()


class Command(BaseCommand):
    help = "Load development data into the database"

    def handle(self, *args, **options):
        User.objects.all().delete()
        Skill.objects.all().delete()
        SkillFactory(title="Teamwork")
        SkillFactory(title="Leadership")
        SkillFactory(title="Organization")
        SkillFactory(title="Planning")
        SkillFactory(title="Engineering")

        Position.objects.all().delete()
        Organization.objects.all().delete()

        admin_user = UserFactory(email="admin@admin.com", password="admin")

        user = UserFactory(email="user1@email.com", password="password")
        participant = ParticipantFactory(user=user)

        job = JobFactory(participant=participant)

        # Create Participants

        # Create Jobs

        # Create Skills
