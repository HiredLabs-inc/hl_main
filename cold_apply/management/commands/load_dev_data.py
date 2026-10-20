from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management import BaseCommand
from django.utils import timezone

from cold_apply.models import Skill
from pipeline import services
from pipeline.models import Flow
from cold_apply.tests.factories import (
    JobFactory,
    ParticipantFactory,
    SkillFactory,
    UserFactory,
)
from resume.models import Degree, Organization, Position
from userprofile.models import BootCampSession, Profile, ServicePackage

User = get_user_model()


class Command(BaseCommand):
    help = "Load development data into the database"

    def handle(self, *args, **options):
        User.objects.all().delete()

        ServicePackage.objects.all().delete()
        for name in ["Basic", "Managed", "Complete"]:
            ServicePackage.objects.create(name=name)

        admin_user = User.objects.create_superuser(
            username="admin@admin.com", email="admin@admin.com", password="admin"
        )
        EmailAddress.objects.create(user=admin_user, email=admin_user.email, verified=True, primary=True)
        Profile.objects.create(user=admin_user)

        Skill.objects.all().delete()

        SkillFactory(title="Teamwork")
        SkillFactory(title="Leadership")
        SkillFactory(title="Organization")
        SkillFactory(title="Planning")
        SkillFactory(title="Engineering")

        Degree.objects.get_or_create(name="Degree 1", defaults={"abbr": "dg1"})

        Position.objects.all().delete()
        Organization.objects.all().delete()

        # An upcoming session, so the Boot Camp tab has one to assign
        if not BootCampSession.objects.filter(start_date__gte=timezone.localdate()).exists():
            BootCampSession.objects.create(start_date=timezone.localdate() + timedelta(days=45))

        # One participant per flow, plus a second applicant, so every dashboard tab has someone
        flows = ["intake", "intake", "resume-job-search", "boot-camp", "nurture"]
        for i in range(5):
            user = UserFactory(email=f"user{i}@email.com", password="password")
            participant = ParticipantFactory(user=user)
            print(participant.user.profile)
            job = JobFactory(participant=participant)
            services.enroll(user, Flow.objects.get(slug=flows[i]), actor=admin_user)
