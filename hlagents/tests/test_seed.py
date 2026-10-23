from django.test import TestCase

from hlagents.models import AgentConfig, AgentLimits, ProviderConfig
from hlagents.tools import TOOLS


class SeedTest(TestCase):
    def test_provider_agents_and_limits_are_seeded(self):
        provider = ProviderConfig.objects.get(name="Ollama Cloud")
        self.assertEqual((provider.kind, provider.secret_env), ("ollama", "OLLAMA_API_KEY"))

        agents = {a.agent_type: a for a in AgentConfig.objects.all()}
        self.assertEqual(set(agents), {"funding", "outreach"})
        for agent in agents.values():
            self.assertEqual((agent.provider, agent.model, agent.tools), (provider, "gemma4:31b", ["web_search"]))
            self.assertTrue(set(agent.tools) <= set(TOOLS))
        self.assertIn("funding opportunities", agents["funding"].system_prompt)
        self.assertIn("Return ONLY the JSON", agents["outreach"].system_prompt)

        limits = AgentLimits.get()
        self.assertEqual(str(limits.run_cost_cap), "1.00")
        self.assertEqual(limits.tool_costs, {"web_search": "0.008"})
