from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase

from hlagents.models import AgentRun, Lead, TaskConfig
from hlagents.tests.fakes import FakeProvider, answer, make_config, make_provider


def fake_provider(*args):
    # Each run finds the same lead; its URL counts as found (tool_text is mocked)
    return FakeProvider(answer([{"org_name": "Acme", "application_url": "https://acme.example.org/grants"}]))


@mock.patch("hlagents.loop.get_provider", side_effect=fake_provider)
@mock.patch("hlagents.services.tool_text", return_value="https://acme.example.org/grants")
class CompareTest(TestCase):
    def setUp(self):
        self.config = make_config()

    def compare(self, *args):
        out = StringIO()
        call_command("hlagents_compare", "--agent", self.config.name, "--models", "a, b", *args, stdout=out)
        return out.getvalue()

    def test_each_model_starts_from_the_same_leads(self, *mocks):
        out = self.compare()
        self.assertIn("a | done | 1 | 0 | 0 | 250 | 0 | Inserted 1.", out)
        self.assertIn("b | done | 1 | 0 | 0 | 250 | 0 | Inserted 1.", out)
        self.assertEqual((AgentRun.objects.count(), Lead.objects.count()), (0, 0))

    def test_keep(self, *mocks):
        out = self.compare("--keep")
        self.assertIn("Skipped: 1 already known.", out)
        self.assertEqual(list(AgentRun.objects.order_by("pk").values_list("model", flat=True)), ["a", "b"])
        self.assertEqual(Lead.objects.count(), 1)

    def test_provider_and_search_model(self, tool_text, get_provider):
        other = make_provider(name="Other")
        seen = []

        def provider(config, *args):
            seen.append((config, TaskConfig.objects.get(key="web_search").model))
            return fake_provider()

        get_provider.side_effect = provider
        self.compare("--provider", "Other", "--search-model", "search-lite", "--keep")

        self.assertEqual(seen, [(other, "search-lite"), (other, "search-lite")])
        self.assertEqual(set(AgentRun.objects.values_list("provider__name", flat=True)), {"Other"})
        # The agent and the task keep their own settings
        self.config.refresh_from_db()
        self.assertNotEqual(self.config.provider, other)
        self.assertNotEqual(TaskConfig.objects.get(key="web_search").model, "search-lite")

    def test_unknown_provider(self, *mocks):
        with self.assertRaisesMessage(CommandError, "No provider named Nope."):
            self.compare("--provider", "Nope")
