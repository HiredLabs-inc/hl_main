import json
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from hlagents import services
from hlagents.loop import run_agent
from hlagents.models import AgentLimits, AgentRun, Lead
from hlagents.tests.fakes import FUNDERS, FakeProvider, answer, make_config, make_provider, make_run, tool_call

SEARCH_RESULTS = {"results": [{"title": "Acme grants", "url": "https://acme.example.org"}]}


@override_settings(TAVILY_API_KEY="tavily-key")
@mock.patch("hlagents.tools.web_search.TavilyClient")
class RunAgentTest(TestCase):
    def test_tool_call_then_answer_saves_leads(self, tavily):
        tavily.return_value.search.return_value = SEARCH_RESULTS
        run = make_run()
        provider = FakeProvider(tool_call(query="veteran grants"), answer(FUNDERS, fenced=True))

        run_agent(run, provider)

        run.refresh_from_db()
        self.assertEqual(run.status, AgentRun.Status.DONE)
        self.assertEqual(run.result, "Inserted 2, skipped 0 (duplicate or incomplete).")
        tavily.assert_called_once_with(api_key="tavily-key")
        tavily.return_value.search.assert_called_once_with(query="veteran grants", max_results=5)
        self.assertEqual(
            [m["role"] for m in run.messages], ["system", "user", "assistant", "tool", "assistant"]
        )
        self.assertEqual(run.messages[3], {"role": "tool", "tool_name": "web_search", "content": json.dumps(SEARCH_RESULTS)})
        self.assertEqual((run.iterations, run.tool_calls, run.input_tokens, run.output_tokens), (2, 1, 300, 70))

        leads = Lead.objects.order_by("dedupe_key")
        self.assertEqual([l.dedupe_key for l in leads], ["acme foundation", "bolt giving"])
        acme = leads[0]
        self.assertEqual((acme.kind, acme.source, acme.review_status), ("funding", "agent", "new"))
        self.assertEqual((acme.funding_amount, acme.url, acme.source_run), ("50000", "https://acme.example.org/grants", run))

    def test_sends_model_and_tool_schema_with_description_override(self, tavily):
        config = make_config(tool_descriptions={"web_search": "Search for grants."})
        provider = FakeProvider(answer([]))

        run_agent(make_run(config), provider)

        call = provider.calls[0]
        self.assertEqual(call["model"], "test-model")
        self.assertEqual([t["function"]["name"] for t in call["tools"]], ["web_search"])
        self.assertEqual(call["tools"][0]["function"]["description"], "Search for grants.")
        self.assertEqual(call["messages"][1], {"role": "user", "content": "Find 2 things."})

    def test_tools_not_enabled_on_the_config_are_not_offered(self, tavily):
        provider = FakeProvider(answer([]))
        run_agent(make_run(make_config(tools=[])), provider)
        self.assertEqual(provider.calls[0]["tools"], [])

    def test_unknown_or_disabled_tool_returns_an_error_to_the_model(self, tavily):
        run = make_run(make_config(tools=[]))
        run_agent(run, FakeProvider(tool_call(name="web_search"), tool_call(name="shell"), answer([])))

        errors = [json.loads(m["content"]) for m in run.messages if m["role"] == "tool"]
        self.assertEqual(errors, [{"error": "There is no tool named web_search."}, {"error": "There is no tool named shell."}])
        self.assertEqual(run.status, AgentRun.Status.DONE)
        tavily.assert_not_called()

    def test_tool_exception_returns_an_error_to_the_model(self, tavily):
        tavily.return_value.search.side_effect = RuntimeError("rate limited")
        run = make_run()
        run_agent(run, FakeProvider(tool_call(), answer([])))

        self.assertEqual(json.loads(run.messages[3]["content"]), {"error": "rate limited"})
        self.assertEqual(run.status, AgentRun.Status.DONE)

    def test_arguments_as_a_json_string(self, tavily):
        tavily.return_value.search.return_value = SEARCH_RESULTS
        call = tool_call()
        call.message["tool_calls"][0]["function"]["arguments"] = '{"query": "grants"}'
        run_agent(make_run(), FakeProvider(call, answer([])))
        tavily.return_value.search.assert_called_once_with(query="grants", max_results=5)

    @override_settings(TAVILY_API_KEY="")
    def test_missing_tavily_key_returns_an_error_to_the_model(self, tavily):
        run = make_run()
        run_agent(run, FakeProvider(tool_call(), answer([])))
        self.assertEqual(json.loads(run.messages[3]["content"]), {"error": "TAVILY_API_KEY isn't set."})

    def test_unparseable_answer_fails_and_keeps_the_reply(self, tavily):
        run = make_run()
        run_agent(run, FakeProvider(answer("Sorry, nothing found.")))

        run.refresh_from_db()
        self.assertEqual(run.status, AgentRun.Status.FAILED)
        self.assertIn("isn't valid JSON", run.error)
        self.assertEqual(run.messages[-1]["content"], "Sorry, nothing found.")

    def test_stops_at_max_iterations(self, tavily):
        run = make_run(make_config(max_iterations=2))
        provider = FakeProvider(tool_call(), tool_call(), answer([]))

        run_agent(run, provider)

        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(run.status, AgentRun.Status.FAILED)
        self.assertEqual(run.error, "Stopped after 2 steps without a final answer.")

    def test_provider_error_fails_the_run_and_keeps_history(self, tavily):
        run = make_run()

        class Broken(FakeProvider):
            def chat(self, model, messages, tools):
                if self.calls:
                    raise ConnectionError("provider down")
                return super().chat(model, messages, tools)

        run_agent(run, Broken(tool_call()))

        run.refresh_from_db()
        self.assertEqual(run.status, AgentRun.Status.FAILED)
        self.assertEqual(run.error, "provider down")
        self.assertEqual([m["role"] for m in run.messages], ["system", "user", "assistant", "tool"])

    @override_settings(HLAGENTS_PROVIDER_SECRETS=["HLAGENTS_TEST_UNSET_KEY"])
    def test_missing_provider_key_fails_the_run(self, tavily):
        provider = make_provider(secret_env="HLAGENTS_TEST_UNSET_KEY")
        run = make_run(make_config(provider=provider))

        run_agent(run)

        self.assertEqual(run.status, AgentRun.Status.FAILED)
        self.assertEqual(run.error, f"HLAGENTS_TEST_UNSET_KEY isn't set, so {provider} can't be used.")


@mock.patch("hlagents.tools.web_search.TavilyClient")
class CostCapTest(TestCase):
    def setUp(self):
        self.limits = AgentLimits.get()
        self.limits.tool_costs = {"web_search": "0.01"}
        self.limits.save()
        # $1 per million input tokens, $2 per million output tokens
        self.config = make_config(provider=make_provider(input_cost_per_mtok=1, output_cost_per_mtok=2))

    def test_cost_counts_tokens_and_tool_calls(self, tavily):
        self.limits.run_cost_cap = Decimal("5.00")
        self.limits.save()
        run = make_run(self.config)
        run_agent(run, FakeProvider(tool_call(tokens=(1_000_000, 0)), answer([], tokens=(0, 500_000))))
        # $1 input + $1 output + $0.01 search
        self.assertEqual(run.cost, Decimal("2.01"))

    def test_stops_at_the_run_cap(self, tavily):
        self.limits.run_cost_cap = Decimal("0.02")
        self.limits.save()
        run = make_run(self.config)
        provider = FakeProvider(tool_call(tokens=(0, 0)), tool_call(tokens=(0, 0)), answer([]))

        run_agent(run, provider)

        run.refresh_from_db()
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(run.status, AgentRun.Status.CAPPED)
        self.assertEqual(run.error, "Stopped at the cost cap.")
        self.assertEqual(run.cost, Decimal("0.02"))

    def test_stops_at_the_daily_cap(self, tavily):
        self.limits.daily_cost_cap = Decimal("5.00")
        self.limits.save()
        earlier = make_run(self.config)
        earlier.cost = Decimal("5.00")
        earlier.save()
        run = make_run(self.config)
        provider = FakeProvider(answer([]))

        run_agent(run, provider)

        self.assertEqual(provider.calls, [])
        self.assertEqual(run.status, AgentRun.Status.CAPPED)


class SaveLeadsTest(TestCase):
    def test_dedupes_within_and_across_runs(self):
        first = make_run()
        self.assertEqual(services.save_leads(first, FUNDERS + [{"org_name": "ACME foundation"}]), (2, 1))

        second = make_run()
        self.assertEqual(services.save_leads(second, [{"org_name": "Bolt Giving"}, {"org_name": "Cora Fund"}]), (1, 1))
        self.assertEqual(Lead.objects.get(dedupe_key="cora fund").source_run, second)

    def test_rejected_leads_still_block_duplicates(self):
        run = make_run()
        services.save_leads(run, FUNDERS[:1])
        Lead.objects.update(review_status=Lead.ReviewStatus.REJECTED)
        self.assertEqual(services.save_leads(make_run(), FUNDERS[:1]), (0, 1))

    def test_same_key_in_another_kind_is_not_a_duplicate(self):
        Lead.objects.create(kind=Lead.Kind.OUTREACH, dedupe_key="acme foundation")
        self.assertEqual(services.save_leads(make_run(), FUNDERS[:1]), (1, 0))

    def test_outreach_skips_missing_and_invalid_emails(self):
        run = make_run(make_config("outreach"))
        candidates = [
            {"first_name": "Pat", "org_name": "DAV", "contact_email": "Pat@DAV.org"},
            {"first_name": "Sam", "org_name": "VFW", "contact_email": ""},
            {"first_name": "Lee", "org_name": "VVA", "contact_email": "not an email"},
            {"first_name": "Pat", "org_name": "DAV", "contact_email": "pat@dav.org"},
        ]
        self.assertEqual(services.save_leads(run, candidates), (1, 3))
        lead = Lead.objects.get()
        self.assertEqual((lead.kind, lead.contact_email, lead.first_name), ("outreach", "pat@dav.org", "Pat"))

    def test_long_values_are_truncated(self):
        services.save_leads(make_run(), [{"org_name": "x" * 300, "funding_amount": "9" * 200}])
        lead = Lead.objects.get()
        self.assertEqual((len(lead.org_name), len(lead.funding_amount)), (255, 100))


class CreateRunTest(TestCase):
    def test_snapshots_provider_model_and_prompt(self):
        config = make_config()
        run = make_run(config, request="Only foundations in Texas.")
        config.model = "other-model"
        config.save()

        run.refresh_from_db()
        self.assertEqual((run.provider, run.model, run.status), (config.provider, "test-model", AgentRun.Status.QUEUED))
        self.assertEqual(
            run.messages,
            [{"role": "system", "content": "You find things."}, {"role": "user", "content": "Only foundations in Texas."}],
        )
