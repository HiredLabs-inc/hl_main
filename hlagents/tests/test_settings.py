from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from background_tasks.models import Task
from hlagents import services
from hlagents.loop import run_agent
from hlagents.models import AgentConfig, AgentLimits, AgentRun, ProviderConfig
from hlagents.tests.fakes import FakeProvider, answer, make_config, make_provider, tool_call


class SettingsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("ada@example.com", "ada@example.com", "pw", is_staff=True)
        cls.admin.groups.add(Group.objects.get(name="Agents"), Group.objects.get(name="Agent admins"))
        cls.agent_user = User.objects.create_user("sam@example.com", "sam@example.com", "pw", is_staff=True)
        cls.agent_user.groups.add(Group.objects.get(name="Agents"))
        cls.provider = make_provider()
        cls.config = make_config(provider=cls.provider)

    def setUp(self):
        self.client.force_login(self.admin)

    def agent_data(self, **kwargs):
        return {
            "name": self.config.name,
            "agent_type": "funding",
            "provider": self.provider.pk,
            "model": "test-model",
            "default_request": "Find 2 things.",
            "system_prompt": "You find things.",
            "tools": ["web_search"],
            "description_web_search": "",
            "max_iterations": 15,
            "active": "on",
            **kwargs,
        }


class SettingsPermissionTest(SettingsTestCase):
    def test_agents_group_cant_see_settings(self):
        self.client.force_login(self.agent_user)
        self.assertNotContains(self.client.get(reverse("hlagents:index")), reverse("hlagents:settings"))
        for url in (
            reverse("hlagents:settings"),
            reverse("hlagents:agent_settings", args=[self.config.pk]),
            reverse("hlagents:new_agent"),
            reverse("hlagents:provider_settings", args=[self.provider.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_agent_admins_see_settings(self):
        self.assertContains(self.client.get(reverse("hlagents:index")), reverse("hlagents:settings"))
        response = self.client.get(reverse("hlagents:settings"))
        self.assertContains(response, self.config.name)
        self.assertContains(response, self.provider.name)
        self.assertContains(response, 'name="run_cost_cap"')

    def test_limits_need_their_own_permission(self):
        editor = User.objects.create_user("ed@example.com", "ed@example.com", "pw")
        editor.user_permissions.add(*Group.objects.get(name="Agent admins").permissions.exclude(codename="change_agentlimits"))
        self.client.force_login(editor)
        response = self.client.get(reverse("hlagents:settings"))
        self.assertNotContains(response, 'name="run_cost_cap"')
        self.assertEqual(self.client.post(reverse("hlagents:settings"), {"run_cost_cap": "0"}).status_code, 403)


@mock.patch("hlagents.services.queue_task", side_effect=lambda *args: Task.objects.create(target_path="/", payload={}))
class AgentSettingsTest(SettingsTestCase):
    def test_changing_the_model_changes_the_next_run(self, queue_task):
        old_run = services.start_run(self.config, self.admin)
        response = self.client.post(
            reverse("hlagents:agent_settings", args=[self.config.pk]),
            self.agent_data(model="bigger-model", description_web_search="Search for grants."),
        )
        self.assertRedirects(response, reverse("hlagents:settings"))
        self.config.refresh_from_db()
        self.assertEqual(self.config.tool_descriptions, {"web_search": "Search for grants."})

        new_run = services.start_run(self.config, self.admin)
        provider = FakeProvider(answer([]))
        run_agent(new_run, provider)

        self.assertEqual(provider.calls[0]["model"], "bigger-model")
        self.assertEqual(provider.calls[0]["tools"][0]["function"]["description"], "Search for grants.")
        old_run.refresh_from_db()
        self.assertEqual(old_run.model, "test-model")

    def test_type_cant_change_once_created(self, queue_task):
        self.client.post(reverse("hlagents:agent_settings", args=[self.config.pk]), self.agent_data(agent_type="outreach"))
        self.config.refresh_from_db()
        self.assertEqual(self.config.agent_type, "funding")

    def test_blank_description_removes_the_override(self, queue_task):
        AgentConfig.objects.filter(pk=self.config.pk).update(tool_descriptions={"web_search": "Old."})
        self.client.post(reverse("hlagents:agent_settings", args=[self.config.pk]), self.agent_data())
        self.config.refresh_from_db()
        self.assertEqual(self.config.tool_descriptions, {})

    def test_inactive_providers_arent_offered(self, queue_task):
        off = make_provider(active=False)
        response = self.client.post(reverse("hlagents:agent_settings", args=[self.config.pk]), self.agent_data(provider=off.pk))
        self.assertContains(response, "Select a valid choice")

    def test_copy_makes_a_new_agent(self, queue_task):
        response = self.client.get(reverse("hlagents:new_agent"), {"copy": self.config.pk})
        self.assertContains(response, f'value="{self.config.name} (copy)"')
        self.assertContains(response, "You find things.")

        response = self.client.post(
            reverse("hlagents:new_agent"), self.agent_data(name="Funding, bigger model", model="bigger-model")
        )
        self.assertRedirects(response, reverse("hlagents:settings"))
        self.assertEqual(AgentConfig.objects.get(name="Funding, bigger model").model, "bigger-model")


class ProviderSettingsTest(SettingsTestCase):
    def provider_data(self, **kwargs):
        return {
            "name": self.provider.name,
            "kind": "ollama",
            "base_url": "",
            "secret_env": "OLLAMA_API_KEY",
            "input_cost_per_mtok": "0.5",
            "output_cost_per_mtok": "1.5",
            "active": "on",
            **kwargs,
        }

    def test_edit_rates_and_key(self):
        response = self.client.post(reverse("hlagents:provider_settings", args=[self.provider.pk]), self.provider_data())
        self.assertRedirects(response, reverse("hlagents:settings"))
        self.provider.refresh_from_db()
        self.assertEqual((self.provider.secret_env, self.provider.output_cost_per_mtok), ("OLLAMA_API_KEY", Decimal("1.5")))

    def test_only_allowed_key_names(self):
        response = self.client.post(
            reverse("hlagents:provider_settings", args=[self.provider.pk]), self.provider_data(secret_env="SECRET_KEY")
        )
        self.assertContains(response, "Select a valid choice")

    def test_negative_rates_are_refused(self):
        response = self.client.post(
            reverse("hlagents:provider_settings", args=[self.provider.pk]), self.provider_data(input_cost_per_mtok="-1")
        )
        self.assertContains(response, "greater than or equal to 0")

    def test_turning_a_provider_off_stops_new_runs(self):
        self.client.post(reverse("hlagents:provider_settings", args=[self.provider.pk]), self.provider_data(secret_env="", active=""))
        response = self.client.get(reverse("hlagents:index"))
        self.assertContains(response, f"{self.provider.name} is turned off in settings.")
        response = self.client.post(
            reverse("hlagents:start_run", args=[self.config.pk]), {f"agent-{self.config.pk}-request": "x"}, follow=True
        )
        self.assertContains(response, "is turned off in settings")
        self.assertFalse(AgentRun.objects.exists())

    def test_new_provider(self):
        response = self.client.post(reverse("hlagents:new_provider"), self.provider_data(name="Local Ollama", secret_env=""))
        self.assertRedirects(response, reverse("hlagents:settings"))
        self.assertTrue(ProviderConfig.objects.filter(name="Local Ollama").exists())


class LimitsTest(SettingsTestCase):
    def test_lowering_the_cap_stops_a_run(self):
        response = self.client.post(
            reverse("hlagents:settings"), {"run_cost_cap": "0.01", "daily_cost_cap": "10", "tool_cost_web_search": "0.02", "tool_cost_read_page": "0"}
        )
        self.assertRedirects(response, reverse("hlagents:settings"))
        limits = AgentLimits.get()
        self.assertEqual((limits.run_cost_cap, limits.tool_costs["web_search"]), (Decimal("0.01"), "0.02"))

        run = services.create_run(self.config, self.admin)
        with mock.patch("hlagents.tools.web_search.TavilyClient"):
            run_agent(run, FakeProvider(tool_call(), answer([])))
        self.assertEqual(run.status, AgentRun.Status.CAPPED)
        self.assertEqual(run.tool_calls, 1)

    def test_negative_cap_is_refused(self):
        response = self.client.post(
            reverse("hlagents:settings"), {"run_cost_cap": "-1", "daily_cost_cap": "10", "tool_cost_web_search": "0", "tool_cost_read_page": "0"}
        )
        self.assertContains(response, "greater than or equal to 0")
