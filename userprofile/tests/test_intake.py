from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from pipeline import services
from pipeline.models import Activity, Enrollment, Flow
from userprofile.intake import start_intake
from userprofile.models import Profile

from .test_onboarding import verified_user
from .test_service_doc import reviewer


class VerifyAndAdvanceTest(TestCase):
    def setUp(self):
        self.vet = verified_user()
        self.profile = Profile.objects.create(user=self.vet)
        self.enrollment = start_intake(self.vet)
        self.url = reverse("userprofile:veteran_status_update_view", args=[self.vet.pk])
        self.reviewer = reviewer()
        self.client.force_login(self.reviewer)

    def test_button_shown_while_awaiting_review(self):
        self.assertContains(self.client.get(self.url), "Verified, move to Triage")

    def test_verify_and_advance(self):
        response = self.client.post(self.url, {"verify_and_advance": ""})
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.veteran_verified)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.current_step.title, "Triage")
        change = Activity.objects.get(enrollment=self.enrollment, kind="step_change")
        self.assertEqual((change.actor, change.to_value), (self.reviewer, "Triage"))
        self.assertNotContains(self.client.get(self.url), "Verified, move to")

    def test_not_awaiting_review_changes_nothing(self):
        services.move_to_step(self.enrollment, self.enrollment.current_step.next_step(), self.reviewer)
        response = self.client.post(self.url, {"verify_and_advance": ""})
        self.assertIn("aren't waiting", str(list(get_messages(response.wsgi_request))[0]))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.veteran_verified)

    def test_only_intake_counts(self):
        Enrollment.objects.all().delete()
        services.enroll(self.vet, Flow.objects.get(slug="boot-camp"), actor=None)
        self.assertNotContains(self.client.get(self.url), "Verified, move to")

    def test_staff_without_permission_cannot_advance(self):
        self.client.force_login(verified_user("staff@example.com", is_staff=True))
        self.assertEqual(self.client.post(self.url, {"verify_and_advance": ""}).status_code, 403)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.current_step.title, "Verify Veteran Status")
