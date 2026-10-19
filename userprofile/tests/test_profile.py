from django.contrib.auth import get_user_model
from django.test import TestCase

from cold_apply.models import Participant, Phase, Step
from cold_apply.tests.factories import UserFactory
from userprofile.models import Profile, ServicePackage


class HandleOnboardCompleteTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        phase = Phase.objects.create(title="Phase 1", start="start", end="end", result="result", order=1)
        cls.first_step = Step.objects.create(title="First", description="First", phase=phase, order=1)
        cls.later_step = Step.objects.create(title="Later", description="Later", phase=phase, order=2)

    def test_creates_participant_on_first_step(self):
        user = UserFactory()
        user.profile.handle_onboard_complete()
        self.assertEqual(user.participant.current_step, self.first_step)
        self.assertTrue(user.profile.is_onboarded)

    def test_keeps_existing_participant(self):
        user = UserFactory()
        participant = Participant.objects.create(user=user, current_step=self.later_step)
        user.profile.handle_onboard_complete()
        participant.refresh_from_db()
        self.assertEqual(participant.current_step, self.later_step)
        self.assertEqual(Participant.objects.filter(user=user).count(), 1)


class ServicePackageDefaultTest(TestCase):
    def test_profile_saves_without_any_packages(self):
        self.assertFalse(ServicePackage.objects.exists())
        user = get_user_model().objects.create_user(username="new@example.com", email="new@example.com")
        profile = Profile.objects.create(user=user)
        self.assertIsNone(profile.service_package)
