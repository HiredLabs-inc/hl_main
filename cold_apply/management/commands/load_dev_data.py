from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from cold_apply.models import Participant, Phase, Skill, Step
from cold_apply.tests.factories import (
    JobFactory,
    ParticipantFactory,
    SkillFactory,
    UserFactory,
)
from resume.models import Degree, Organization, Position
from userprofile.models import Profile, ServicePackage

User = get_user_model()


class Command(BaseCommand):
    help = "Load development data into the database"

    def handle(self, *args, **options):
        User.objects.all().delete()
        Phase.objects.all().delete()

        admin_user = User.objects.create_superuser(
            username="admin@admin.com", email="admin@admin.com", password="admin"
        )
        Profile.objects.create(user=admin_user)

        phase_1 = Phase.objects.create(
            title="Phase 1",
            start="Participant Shows Interest",
            end="Intake call completed",
            result="Clear direction for job search and resume type",
            active=True,
            order=0,
        )
        phase_2 = Phase.objects.create(
            title="Phase 2",
            start="Full results of intake call and phase 1 analysis received",
            end="Hired Labs approves of initial job set and tailored resume sets",
            result="First actionable set of open jobs and tailored resumes ready for transmission to participant",
            active=True,
            order=1,
        )
        phase_3 = Phase.objects.create(
            title="Phase 3",
            start="Initial set of jobs and resumes sent to participant",
            end="Changes made to general format of resume or direction of job search",
            result="Initial set of jobs and resumes agreed upon by Hired Labs and participant",
            active=True,
            order=2,
        )

        Step.objects.create(title="Phase 1.0", phase=phase_1, order=0)
        Step.objects.create(title="Phase 1.1", phase=phase_1, order=1)
        Step.objects.create(title="Phase 2.0", phase=phase_2, order=0)
        Step.objects.create(title="Phase 2.1", phase=phase_2, order=1)
        Step.objects.create(title="Phase 3.0", phase=phase_3, order=0)
        Step.objects.create(title="Phase 3.1", phase=phase_3, order=1)

        Skill.objects.all().delete()

        SkillFactory(title="Teamwork")
        SkillFactory(title="Leadership")
        SkillFactory(title="Organization")
        SkillFactory(title="Planning")
        SkillFactory(title="Engineering")

        Degree.objects.get_or_create(name="Degree 1", defaults={"abbr": "dg1"})

        Position.objects.all().delete()
        Organization.objects.all().delete()

        User.objects.create_superuser(
            username="admin", email="admin@admin.com", password="admin"
        )

        for i in range(5):
            user = UserFactory(email=f"user{i}@email.com", password="password")
            participant = ParticipantFactory(user=user)
            print(participant.user.profile)
            job = JobFactory(participant=participant)

        ServicePackage.objects.all().delete()
        ServicePackage.objects.create(
            name="Basic",
        )
        ServicePackage.objects.create(
            name="Managed",
        )
        ServicePackage.objects.create(
            name="Complete",
        )
