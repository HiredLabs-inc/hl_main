from django.contrib.auth import get_user_model
from django.test import TestCase

from cold_apply.models import Participant
from cold_apply.tests.factories import UserFactory
from pipeline import services
from pipeline.models import Enrollment, Flow
from userprofile.models import Profile, ServicePackage


class HandleOnboardCompleteTest(TestCase):
    def test_creates_participant(self):
        user = UserFactory()
        user.profile.handle_onboard_complete()
        self.assertTrue(Participant.objects.filter(user=user).exists())
        self.assertTrue(user.profile.is_onboarded)

    def test_keeps_existing_participant(self):
        user = UserFactory()
        participant = Participant.objects.create(user=user)
        user.profile.handle_onboard_complete()
        self.assertEqual(list(Participant.objects.filter(user=user)), [participant])

    def test_enrolls_veteran_in_intake_at_verify(self):
        user = UserFactory(profile__is_veteran=True)
        user.profile.handle_onboard_complete()
        enrollment = Enrollment.objects.get(person=user)
        self.assertEqual((enrollment.flow.slug, enrollment.current_step.title), ("intake", "Verify Veteran Status"))
        self.assertEqual(enrollment.activities.get().actor, user)

    def test_non_veteran_skips_to_triage(self):
        user = UserFactory(profile__is_veteran=False)
        user.profile.handle_onboard_complete()
        self.assertEqual(Enrollment.objects.get(person=user).current_step.title, "Triage")

    def test_running_again_does_not_enroll_again(self):
        user = UserFactory()
        user.profile.handle_onboard_complete()
        user.profile.handle_onboard_complete()
        self.assertEqual(Enrollment.objects.filter(person=user).count(), 1)

    def test_people_already_in_a_flow_are_not_put_in_intake(self):
        user = UserFactory()
        services.enroll(user, Flow.objects.get(slug="boot-camp"), actor=None)
        user.profile.handle_onboard_complete()
        self.assertEqual(list(Enrollment.objects.filter(person=user).values_list("flow__slug", flat=True)), ["boot-camp"])

    def test_missing_intake_flow_does_not_block_onboarding(self):
        Flow.objects.filter(slug="intake").delete()
        user = UserFactory()
        with self.assertLogs("userprofile.intake", "ERROR"):
            user.profile.handle_onboard_complete()
        self.assertTrue(Profile.objects.get(user=user).is_onboarded)
        self.assertFalse(Enrollment.objects.exists())


class ServicePackageDefaultTest(TestCase):
    def test_profile_saves_without_any_packages(self):
        self.assertFalse(ServicePackage.objects.exists())
        user = get_user_model().objects.create_user(username="new@example.com", email="new@example.com")
        profile = Profile.objects.create(user=user)
        self.assertIsNone(profile.service_package)
