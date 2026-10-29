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

        gemini = ProviderConfig.objects.get(name="Gemini on Vertex")
        agents = {a.agent_type: a for a in AgentConfig.objects.all()}
        self.assertEqual(set(agents), {"funding", "outreach"})
        for agent in agents.values():
            # 0013 moved them from Ollama Cloud to Gemini
            self.assertEqual((agent.provider, agent.model, agent.tools), (gemini, settings.GEMINI_MODEL, ["web_search", "read_page"]))
            self.assertTrue(set(agent.tools) <= set(TOOLS))
        # 0005 replaced the prototype prompts, and 0007 replaced those
        self.assertIn("Never fill it in from the range in these criteria", agents["funding"].system_prompt)
        self.assertIn("use read_page", agents["funding"].system_prompt)
        # 0013 paced it for Gemini
        self.assertIn("4. Work in parallel", agents["funding"].system_prompt)
        self.assertIn("Return [] only if you haven't read any.", agents["funding"].system_prompt)
        self.assertIn("Use read_page", agents["outreach"].system_prompt)
        self.assertIn("Never construct or guess one", agents["outreach"].system_prompt)
        self.assertNotIn("exactly 10", agents["outreach"].system_prompt)

        limits = AgentLimits.get()
        self.assertEqual(str(limits.run_cost_cap), "1.00")
        self.assertEqual(limits.tool_costs, {"web_search": "0.014", "read_page": "0"})

    def test_gemini_provider_and_tasks_are_seeded(self):
        gemini = ProviderConfig.objects.get(name="Gemini on Vertex")
        self.assertEqual((gemini.kind, gemini.location, gemini.secret_env), ("gemini", "", ""))
        tasks = {t.key: t for t in TaskConfig.objects.all()}
        self.assertEqual(set(tasks), {"resume_overview", "resume_bullets", "bullet_rewrite", "job_keywords", "web_search"})
        for task in tasks.values():
            # 0013 put web_search on a faster model
            model = "gemini-3.5-flash-lite" if task.key == "web_search" else settings.GEMINI_MODEL
            self.assertEqual((task.provider, task.model, task.active), (gemini, model, True))
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


class AgentsOnGeminiTest(TestCase):
    """0013 moves only agents and rates that are still the seeded ones."""

    migration = import_module("hlagents.migrations.0013_agents_on_gemini")

    def test_move_back_and_again(self):
        self.migration.move_back(django_apps, None)
        ollama = ProviderConfig.objects.get(name="Ollama Cloud")
        for agent in AgentConfig.objects.all():
            self.assertEqual((agent.provider, agent.model), (ollama, "gemma4:31b"))
        self.assertEqual(AgentLimits.get().tool_costs, {"web_search": "0.016", "read_page": "0.002"})
        self.assertEqual(TaskConfig.objects.get(key="web_search").model, settings.GEMINI_MODEL)
        funding = AgentConfig.objects.get(agent_type="funding")
        self.assertNotIn("Work in parallel", funding.system_prompt)
        self.assertEqual(funding.system_prompt, import_module("hlagents.migrations.0007_lead_quality").FUNDING_PROMPT)

        self.migration.move(django_apps, None)
        gemini = ProviderConfig.objects.get(name="Gemini on Vertex")
        self.assertEqual(set(AgentConfig.objects.values_list("provider", "model")), {(gemini.pk, settings.GEMINI_MODEL)})
        self.assertEqual(AgentLimits.get().tool_costs, {"web_search": "0.014", "read_page": "0"})
        self.assertEqual(TaskConfig.objects.get(key="web_search").model, "gemini-3.5-flash-lite")

    def test_edited_agents_and_rates_are_kept(self):
        self.migration.move_back(django_apps, None)
        AgentConfig.objects.filter(agent_type="funding").update(model="nemotron-3-ultra", system_prompt="Edited.")
        TaskConfig.objects.filter(key="web_search").update(model="search-edited")
        limits = AgentLimits.get()
        limits.tool_costs = {"web_search": "0.05", "read_page": "0.002"}
        limits.save()

        self.migration.move(django_apps, None)

        funding = AgentConfig.objects.get(agent_type="funding")
        self.assertEqual((funding.provider.name, funding.model, funding.system_prompt), ("Ollama Cloud", "nemotron-3-ultra", "Edited."))
        self.assertEqual(TaskConfig.objects.get(key="web_search").model, "search-edited")
        self.assertEqual(AgentConfig.objects.get(agent_type="outreach").provider.name, "Gemini on Vertex")
        self.assertEqual(AgentLimits.get().tool_costs, {"web_search": "0.05", "read_page": "0.002"})


class ProviderModelsTest(TestCase):
    """0014 lists each provider's models from what its agents and tasks use."""

    migration = import_module("hlagents.migrations.0014_provider_models")

    def test_providers_start_with_the_models_in_use(self):
        self.assertEqual(
            ProviderConfig.objects.get(name="Gemini on Vertex").models, [settings.GEMINI_MODEL, "gemini-3.5-flash-lite"]
        )
        self.assertEqual(ProviderConfig.objects.get(name="Ollama Cloud").models, ["gemma4:31b"])

    def test_seeds_from_edited_agents(self):
        ollama = ProviderConfig.objects.get(name="Ollama Cloud")
        AgentConfig.objects.filter(agent_type="funding").update(provider=ollama, model="nemotron-3-ultra")

        self.migration.seed_models(django_apps, None)

        self.assertEqual(ProviderConfig.objects.get(pk=ollama.pk).models, ["nemotron-3-ultra", "gemma4:31b"])
