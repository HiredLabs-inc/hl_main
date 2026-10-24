from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from cold_apply.models import KeywordAnalysis
from cold_apply.tests.factories import BulletFactory, ExperienceFactory, JobFactory, ParticipantFactory
from cold_apply.text_generation import (
    TextGenerationError,
    generate_bullets,
    generate_overview,
    parse_bullets,
    rewrite_bullet_for_job,
)
from hlagents.models import TaskCall, TaskConfig
from hlagents.providers import ProviderError
from hlagents.tests.fakes import FakeProvider, answer
from resume.models import Bullet, Overview


def fake_provider(*replies):
    """Patches the hlagents tasks to use a FakeProvider with these replies."""
    provider = FakeProvider(*replies)
    patcher = mock.patch("hlagents.completion.get_provider", return_value=provider)
    return provider, patcher


class GenerationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.participant = ParticipantFactory(jobs=[], experiences=[])
        cls.user = cls.participant.user
        cls.job = JobFactory(participant=cls.participant, description="We need a welder who reads blueprints.")
        KeywordAnalysis.objects.create(job=cls.job, unigram="welding", bigram="read blueprints", trigram="mig tig welding")
        cls.experience = ExperienceFactory(participant=cls.participant, bullets=[])
        cls.bullet = BulletFactory(experience=cls.experience, text="Fixed things on ships.")

    def run_with(self, *replies):
        provider, patcher = fake_provider(*replies)
        patcher.start()
        self.addCleanup(patcher.stop)
        return provider

    def user_message(self, provider):
        return provider.calls[0]["messages"][1]["content"]


class GenerateTest(GenerationTestCase):
    def test_overview_for_a_job(self):
        provider = self.run_with(answer("An overview."))
        self.assertEqual(generate_overview(self.job.title, self.job, user=self.user), "An overview.")

        message = self.user_message(provider)
        self.assertIn(f"Job title: {self.job.title.title}", message)
        self.assertIn("welding, read blueprints, mig tig welding", message)
        self.assertIn("We need a welder who reads blueprints.", message)
        self.assertEqual(provider.calls[0]["messages"][0]["content"], TaskConfig.objects.get(key="resume_overview").instructions)
        call = TaskCall.objects.get()
        self.assertEqual((call.config.key, call.user), ("resume_overview", self.user))

    def test_overview_without_a_job(self):
        provider = self.run_with(answer("An overview."))
        generate_overview(self.job.title)
        self.assertEqual(self.user_message(provider), f"Job title: {self.job.title.title}")

    def test_bullets_parse_json_and_stop_at_the_quantity(self):
        provider = self.run_with(answer('["Led a team.", "Built a thing.", "Extra one."]'))
        self.assertEqual(generate_bullets(self.experience, quantity=2), ["Led a team.", "Built a thing."])
        message = self.user_message(provider)
        self.assertIn(f"Write 2 bullet points for this work experience heading:\n{self.experience.position.title}", message)
        self.assertIn("Fixed things on ships.", message)

    def test_bullets_with_no_usable_text_fail(self):
        self.run_with(answer("[]"))
        with self.assertRaises(TextGenerationError):
            generate_bullets(self.experience)

    def test_rewrite_bullet(self):
        provider = self.run_with(answer("Repaired shipboard systems."))
        self.assertEqual(rewrite_bullet_for_job(self.bullet, self.job), "Repaired shipboard systems.")
        message = self.user_message(provider)
        self.assertIn("Bullet point:\nFixed things on ships.", message)
        self.assertIn("Keywords from the job:\nwelding, read blueprints, mig tig welding", message)
        self.assertEqual(TaskCall.objects.get().config.key, "bullet_rewrite")

    def test_failure_names_the_model(self):
        self.run_with(ProviderError("404 model not found"))
        model = TaskConfig.objects.get(key="resume_overview").model
        with self.assertLogs("hlagents.completion", "ERROR"), self.assertRaisesMessage(
            TextGenerationError, f"The LLM failed you. {model} feels shame, but you can try again later."
        ):
            generate_overview(self.job.title)


class ParseBulletsTest(SimpleTestCase):
    def test_json_list(self):
        self.assertEqual(parse_bullets('["One.", " Two. "]'), ["One.", "Two."])

    def test_fenced_json(self):
        self.assertEqual(parse_bullets('```json\n["One.", "Two."]\n```'), ["One.", "Two."])

    def test_lines_with_bullets_and_numbers(self):
        self.assertEqual(parse_bullets("- One.\n* Two.\n3. Three.\n\n• Four."), ["One.", "Two.", "Three.", "Four."])

    def test_json_that_doesnt_parse_falls_back_to_lines(self):
        self.assertEqual(parse_bullets('[\n  "One.",\n  "Two."\n'), ["One.", "Two."])

    def test_pipe_separated(self):
        self.assertEqual(parse_bullets("One. | Two."), ["One.", "Two."])


class GenerationFailureViewTest(GenerationTestCase):
    """A failed generation shows the shame message instead of a 500, and saves nothing."""

    def setUp(self):
        self.client.force_login(self.user)
        TaskConfig.objects.update(model="gemini-test")
        self.run_with(ProviderError("404 model not found"))
        logs = self.assertLogs("hlagents.completion", "ERROR")
        logs.__enter__()
        self.addCleanup(logs.__exit__, None, None, None)

    message = "The LLM failed you. gemini-test feels shame, but you can try again later."

    def test_auto_generated_bullets(self):
        url = reverse("cold_apply:create_bullet", args=[self.participant.pk])
        response = self.client.post(url, {"auto_generate": "True", "quantity": 1, "experience": self.experience.pk})
        self.assertContains(response, self.message)
        self.assertEqual(Bullet.objects.filter(experience=self.experience).count(), 1)
        self.assertEqual(TaskCall.objects.get().user, self.user)

    def test_auto_generated_overview(self):
        url = reverse("cold_apply:create_overview", args=[self.participant.pk, self.job.title_id, self.job.pk])
        response = self.client.post(url, {"auto_generate": "True"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, self.message)
        self.assertFalse(Overview.objects.filter(participant=self.participant).exists())

    def test_regenerate_bullet(self):
        url = reverse("cold_apply:regenerate_bullet", args=[self.bullet.pk, self.job.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.content.decode(), self.message)
        self.bullet.refresh_from_db()
        self.assertEqual(self.bullet.text, "Fixed things on ships.")


class GenerationViewTest(GenerationTestCase):
    def test_auto_generated_bullets_are_saved(self):
        self.client.force_login(self.user)
        self.run_with(answer('["Led a welding crew of six.", "Read blueprints daily."]'))
        url = reverse("cold_apply:create_bullet", args=[self.participant.pk])
        self.client.post(url, {"auto_generate": "True", "quantity": 2, "experience": self.experience.pk})
        new = Bullet.objects.filter(experience=self.experience).exclude(pk=self.bullet.pk)
        self.assertTrue(all(bullet.auto_generated for bullet in new))
        texts = {bullet.text for bullet in new}
        self.assertEqual(texts, {"Led a welding crew of six.", "Read blueprints daily."})
