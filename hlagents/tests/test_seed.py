from importlib import import_module

from django.apps import apps as django_apps
from django.contrib.auth.models import Group
from django.conf import settings
from django.test import TestCase

from hlagents.models import AgentConfig, AgentLimits, ProviderConfig, TaskConfig
from hlagents.tools import TOOLS


class SeedTest(TestCase):
    def test_provider_agents_and_limits_are_seeded(self):
        provider = ProviderConfig.objects.get(name="Ollama Cloud")
        self.assertEqual((provider.kind, provider.secret_env), ("ollama", "OLLAMA_API_KEY"))

        agents = {a.agent_type: a for a in AgentConfig.objects.all()}
        self.assertEqual(set(agents), {"funding", "outreach"})
        for agent in agents.values():
            self.assertEqual((agent.provider, agent.model, agent.tools), (provider, "gemma4:31b", ["web_search", "read_page"]))
            self.assertTrue(set(agent.tools) <= set(TOOLS))
        # 0005 replaced the prototype prompts, and 0007 replaced those
        self.assertIn("Never fill it in from the range in these criteria", agents["funding"].system_prompt)
        self.assertIn("use read_page", agents["funding"].system_prompt)
        self.assertIn("Use read_page", agents["outreach"].system_prompt)
        self.assertIn("Never construct or guess one", agents["outreach"].system_prompt)
        self.assertNotIn("exactly 10", agents["outreach"].system_prompt)

        limits = AgentLimits.get()
        self.assertEqual(str(limits.run_cost_cap), "1.00")
        self.assertEqual(limits.tool_costs, {"web_search": "0.016", "read_page": "0.002"})

    def test_gemini_provider_and_tasks_are_seeded(self):
        gemini = ProviderConfig.objects.get(name="Gemini on Vertex")
        self.assertEqual((gemini.kind, gemini.location, gemini.secret_env), ("gemini", "", ""))
        tasks = {t.key: t for t in TaskConfig.objects.all()}
        self.assertEqual(set(tasks), {"resume_overview", "resume_bullets", "bullet_rewrite", "job_keywords", "web_search"})
        for task in tasks.values():
            self.assertEqual((task.provider, task.model, task.active), (gemini, settings.GEMINI_MODEL, True))
            self.assertEqual(task.options["thinking_budget"], 0)
            # Room for the thinking Gemini does anyway (BUG-049)
            self.assertEqual(task.options["max_output_tokens"], 8192)
        self.assertIn("JSON list of strings", tasks["resume_bullets"].instructions)
        # 0010: keywords run cooler, so refreshing mostly gives the same ones
        self.assertEqual(tasks["job_keywords"].options["temperature"], 0.2)
        self.assertIn("word for word", tasks["job_keywords"].instructions)
        # 0012: the search behind the agents' web_search tool is grounded
        self.assertTrue(tasks["web_search"].options["google_search"])
        self.assertNotIn("google_search", tasks["resume_overview"].options)

    def test_agent_admins_group(self):
        perms = set(Group.objects.get(name="Agent admins").permissions.values_list("codename", flat=True))
        self.assertIn("change_agentlimits", perms)
        self.assertIn("change_agentconfig", perms)


class PromptUpdateTest(TestCase):
    """0005 and 0007 only replace prompts, tools and rates that are still the seeded ones."""

    migration = import_module("hlagents.migrations.0005_agent_admins_and_prompts")
    migration_0007 = import_module("hlagents.migrations.0007_lead_quality")

    def test_edited_prompts_are_kept(self):
        funding = AgentConfig.objects.get(agent_type="funding")
        outreach = AgentConfig.objects.get(agent_type="outreach")
        AgentConfig.objects.filter(pk=funding.pk).update(system_prompt="Edited in settings.")

        self.migration_0007.restore(django_apps, None)
        self.migration.restore_prompts(django_apps, None)

        funding.refresh_from_db()
        outreach.refresh_from_db()
        self.assertEqual(funding.system_prompt, "Edited in settings.")
        self.assertIn("exactly 10", outreach.system_prompt)
        self.assertEqual(outreach.default_request, "Find 10 veteran-serving organizations for outreach partnerships.")

    def test_0007_keeps_edited_tools_and_rates(self):
        outreach = AgentConfig.objects.get(agent_type="outreach")
        AgentConfig.objects.filter(pk=outreach.pk).update(tools=["read_page"])
        limits = AgentLimits.get()
        limits.tool_costs = {"web_search": "0.05", "read_page": "0.002"}
        limits.save()

        self.migration_0007.restore(django_apps, None)

        outreach.refresh_from_db()
        self.assertEqual(outreach.tools, ["read_page"])
        self.assertEqual(AgentConfig.objects.get(agent_type="funding").tools, ["web_search"])
        self.assertEqual(AgentLimits.get().tool_costs, {"web_search": "0.05", "read_page": "0.002"})
