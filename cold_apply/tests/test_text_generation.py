from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from cold_apply.tests.factories import BulletFactory, ExperienceFactory, JobFactory, ParticipantFactory
from cold_apply.text_generation import TextGenerationError, generate_text
from resume.models import Bullet, Overview


def fake_client(text="Generated text", error=None):
    client = mock.Mock()
    if error:
        client.models.generate_content.side_effect = error
    else:
        client.models.generate_content.return_value = mock.Mock(text=text)
    return client


@override_settings(GCP_PROJECT_ID="test-project", GEMINI_MODEL="gemini-test", GEMINI_LOCATION="us-west1")
class GenerateTextTest(TestCase):
    def test_calls_the_configured_model_on_vertex(self):
        client = fake_client("A bullet")
        with mock.patch("cold_apply.text_generation.genai.Client", return_value=client) as client_class:
            self.assertEqual(generate_text("Write a bullet"), "A bullet")
        client_class.assert_called_once_with(vertexai=True, project="test-project", location="us-west1")
        kwargs = client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs["model"], "gemini-test")
        self.assertEqual(kwargs["contents"], "Write a bullet")

    def test_empty_reply_raises(self):
        with mock.patch("cold_apply.text_generation.genai.Client", return_value=fake_client(None)):
            with self.assertRaises(TextGenerationError):
                generate_text("Write a bullet")

    def test_api_error_raises(self):
        client = fake_client(error=RuntimeError("404 model not found"))
        with mock.patch("cold_apply.text_generation.genai.Client", return_value=client):
            with self.assertLogs("cold_apply.text_generation", "ERROR"), self.assertRaises(TextGenerationError):
                generate_text("Write a bullet")


class GenerationFailureViewTest(TestCase):
    """A failed generation shows an error instead of a 500, and saves nothing."""

    @classmethod
    def setUpTestData(cls):
        cls.participant = ParticipantFactory(jobs=[], experiences=[])
        cls.job = JobFactory(participant=cls.participant)
        cls.experience = ExperienceFactory(participant=cls.participant, bullets=[])
        cls.bullet = BulletFactory(experience=cls.experience, text="Original")

    def setUp(self):
        self.client.force_login(self.participant.user)
        patcher = mock.patch(
            "cold_apply.text_generation.generate_text", side_effect=TextGenerationError("Text generation failed.")
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_auto_generated_bullets(self):
        url = reverse("cold_apply:create_bullet", args=[self.participant.pk])
        response = self.client.post(url, {"auto_generate": "True", "quantity": 1, "experience": self.experience.pk})
        self.assertContains(response, "Text generation failed.")
        self.assertEqual(Bullet.objects.filter(experience=self.experience).count(), 1)

    def test_auto_generated_overview(self):
        url = reverse("cold_apply:create_overview", args=[self.participant.pk, self.job.title_id, self.job.pk])
        response = self.client.post(url, {"auto_generate": "True"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "Text generation failed.")
        self.assertFalse(Overview.objects.filter(participant=self.participant).exists())

    def test_regenerate_bullet(self):
        url = reverse("cold_apply:regenerate_bullet", args=[self.bullet.pk, self.job.pk])
        self.assertEqual(self.client.post(url).status_code, 502)
        self.bullet.refresh_from_db()
        self.assertEqual(self.bullet.text, "Original")
