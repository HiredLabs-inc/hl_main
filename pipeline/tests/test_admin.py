from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pipeline import services
from pipeline.models import Flow, Phase, Step


class PipelineAdminTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser("super@example.com", "super@example.com", "password")
        flow = Flow.objects.create(name="Intake", slug="test-intake")
        step = Step.objects.create(phase=Phase.objects.create(flow=flow, title="Applicants"), title="Triage")
        self.enrollment = services.enroll(
            User.objects.create_user("vet@example.com", "vet@example.com"), flow, self.superuser
        )
        self.client.force_login(self.superuser)

    def test_pages_load(self):
        for name in ("flow", "phase", "step", "enrollment", "activity"):
            with self.subTest(model=name):
                url = reverse(f"admin:pipeline_{name}_changelist")
                self.assertEqual(self.client.get(url, {"q": "vet"} if name in ("enrollment", "activity") else {}).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:pipeline_flow_add")).status_code, 200)

    def test_enrollments_are_read_only(self):
        self.assertEqual(self.client.get(reverse("admin:pipeline_enrollment_add")).status_code, 403)
        response = self.client.post(
            reverse("admin:pipeline_enrollment_delete", args=[self.enrollment.pk]), {"post": "yes"}
        )
        self.assertEqual(response.status_code, 403)
