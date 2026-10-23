from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from hlagents.models import AgentRun, Lead
from hlagents.tests.fakes import FakeProvider, answer, make_config


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
        self.assertIn("a | done | 1 | 0 | 250 | 0 | Inserted 1.", out)
        self.assertIn("b | done | 1 | 0 | 250 | 0 | Inserted 1.", out)
        self.assertEqual((AgentRun.objects.count(), Lead.objects.count()), (0, 0))

    def test_keep(self, *mocks):
        out = self.compare("--keep")
        self.assertIn("Skipped: 1 already known.", out)
        self.assertEqual(list(AgentRun.objects.order_by("pk").values_list("model", flat=True)), ["a", "b"])
        self.assertEqual(Lead.objects.count(), 1)
