import json
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from hlagents import services
from hlagents.loop import run_agent
from hlagents.models import AgentLimits, AgentRun, Lead
from hlagents.tests.fakes import FUNDERS, FakeProvider, answer, cite, make_config, make_provider, make_run, tool_call

SEARCH_RESULTS = [
    {"title": "Acme grants", "url": "https://acme.example.org/grants", "content": "Workforce grants."},
    {"title": "Bolt giving", "url": "https://www.bolt.example.org/giving/", "content": "Tech education."},
]
TRIMMED_RESULTS = {"results": SEARCH_RESULTS}


@mock.patch("hlagents.tools.web_search.search", return_value=(SEARCH_RESULTS, ""))
class RunAgentTest(TestCase):
    def test_tool_call_then_answer_saves_leads(self, search):
        run = make_run()
        provider = FakeProvider(tool_call(query="veteran grants"), answer(FUNDERS, fenced=True))

        run_agent(run, provider)

        run.refresh_from_db()
        self.assertEqual(run.status, AgentRun.Status.DONE)
        self.assertEqual(run.result, "Inserted 2.")
        search.assert_called_once_with("veteran grants", 8)
        self.assertEqual(
            [m["role"] for m in run.messages], ["system", "user", "assistant", "tool", "assistant"]
        )
        self.assertEqual(run.messages[3], {"role": "tool", "tool_name": "web_search", "content": json.dumps(TRIMMED_RESULTS)})
        self.assertEqual((run.iterations, run.tool_calls, run.input_tokens, run.output_tokens), (2, 1, 300, 70))

        leads = Lead.objects.order_by("dedupe_key")
        self.assertEqual([l.dedupe_key for l in leads], ["acme foundation", "bolt giving"])
        acme = leads[0]
        self.assertEqual((acme.kind, acme.source, acme.review_status), ("funding", "agent", "new"))
        self.assertEqual((acme.funding_amount, acme.url, acme.source_run), ("50000", "https://acme.example.org/grants", run))

    def test_sends_model_and_tool_schema_with_description_override(self, search):
        config = make_config(tool_descriptions={"web_search": "Search for grants."})
        provider = FakeProvider(answer([]))

        run_agent(make_run(config), provider)

        call = provider.calls[0]
        self.assertEqual(call["model"], "test-model")
        self.assertEqual([t["function"]["name"] for t in call["tools"]], ["web_search"])
        self.assertTrue(call["messages"][0]["content"].startswith("You find things.\n\nToday is "))
        self.assertEqual(call["tools"][0]["function"]["description"], "Search for grants. Snippets leave out links and email addresses: read the page for those.")
        self.assertEqual(call["messages"][1], {"role": "user", "content": "Find 2 things."})

    def test_tools_not_enabled_on_the_config_are_not_offered(self, search):
        provider = FakeProvider(answer([]))
        run_agent(make_run(make_config(tools=[])), provider)
        self.assertEqual(provider.calls[0]["tools"], [])

    def test_unknown_or_disabled_tool_returns_an_error_to_the_model(self, search):
        run = make_run(make_config(tools=[]))
        run_agent(run, FakeProvider(tool_call(name="web_search"), tool_call(name="shell"), answer([])))

        errors = [json.loads(m["content"]) for m in run.messages if m["role"] == "tool"]
        self.assertEqual(errors, [{"error": "There is no tool named web_search."}, {"error": "There is no tool named shell."}])
        self.assertEqual(run.status, AgentRun.Status.DONE)
        search.assert_not_called()

    def test_tool_exception_returns_an_error_to_the_model(self, search):
        search.side_effect = RuntimeError("rate limited")
        run = make_run()
        run_agent(run, FakeProvider(tool_call(), answer([])))

        self.assertEqual(json.loads(run.messages[3]["content"]), {"error": "rate limited"})
        self.assertEqual(run.status, AgentRun.Status.DONE)

    def test_arguments_as_a_json_string(self, search):
        call = tool_call()
        call.message["tool_calls"][0]["function"]["arguments"] = '{"query": "grants"}'
        run_agent(make_run(), FakeProvider(call, answer([])))
        search.assert_called_once_with("grants", 8)

    def test_search_suggestions_are_kept_beside_the_reply_for_the_run_page(self, search):
        search.return_value = (SEARCH_RESULTS, "<div>chips</div>")
        run = make_run()
        run_agent(run, FakeProvider(tool_call(), answer([])))

        reply = run.messages[3]
        self.assertEqual(reply["suggestions"], "<div>chips</div>")
        # The model is sent the content only
        self.assertEqual(json.loads(reply["content"]), TRIMMED_RESULTS)

    def test_unparseable_answer_is_sent_back_once(self, search):
        run = make_run()
        provider = FakeProvider(answer("Sorry, nothing found."), answer([]))

        run_agent(run, provider)

        self.assertEqual(run.status, AgentRun.Status.DONE)
        self.assertEqual(run.messages[-2]["note"], "Fix the JSON")
        self.assertIn("isn't valid JSON", run.messages[-2]["content"])
        self.assertEqual(provider.calls[1]["messages"][-1], run.messages[-2])

    def test_unparseable_answer_twice_fails_and_keeps_the_reply(self, search):
        run = make_run()
        run_agent(run, FakeProvider(answer("Sorry, nothing found."), answer("Still nothing.")))

        run.refresh_from_db()
        self.assertEqual(run.status, AgentRun.Status.FAILED)
        self.assertIn("isn't valid JSON", run.error)
        self.assertEqual(run.messages[-1]["content"], "Still nothing.")

    def test_last_step_offers_no_tools_so_the_agent_answers(self, search):
        run = make_run(make_config(max_iterations=2))
        provider = FakeProvider(tool_call(), answer(FUNDERS[:1]))

        run_agent(run, provider)

        self.assertEqual(run.status, AgentRun.Status.DONE)
        self.assertEqual(len(provider.calls[0]["tools"]), 1)
        self.assertEqual(provider.calls[1]["tools"], [])
        self.assertEqual(provider.calls[1]["messages"][-1]["note"], "Step limit")
        self.assertEqual(Lead.objects.count(), 1)

    def test_tool_calls_on_the_last_step_are_ignored(self, search):
        run = make_run(make_config(max_iterations=2))
        last = answer(FUNDERS[:1])
        last.message["tool_calls"] = tool_call().message["tool_calls"]
        provider = FakeProvider(tool_call(), last)

        run_agent(run, provider)

        self.assertEqual(len(provider.calls), 2)
        self.assertEqual((run.status, run.tool_calls), (AgentRun.Status.DONE, 1))
        self.assertNotIn("tool_calls", run.messages[-1])
        self.assertEqual(Lead.objects.count(), 1)

    def test_stops_at_max_iterations(self, search):
        # A config without tools has none to withhold on the last step
        run = make_run(make_config(max_iterations=2, tools=[]))
        provider = FakeProvider(tool_call(), tool_call(), answer([]))

        run_agent(run, provider)

        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(run.status, AgentRun.Status.FAILED)
        self.assertEqual(run.error, "Stopped after 2 steps without a final answer.")

    def test_rejected_candidates_are_sent_back_once(self, search):
        run = make_run()
        made_up = {**FUNDERS[0], "org_name": "Made Up Fund", "application_url": "https://made.up/grants"}
        home_page = {**FUNDERS[0], "org_name": "Cora Fund", "application_url": "https://cora.example.org/"}
        fixed = {**FUNDERS[1]}
        provider = FakeProvider(
            tool_call(), answer([FUNDERS[0], made_up, home_page]), answer([fixed, made_up]),
        )

        run_agent(run, provider)

        self.assertEqual(run.status, AgentRun.Status.DONE)
        self.assertEqual(len(provider.calls), 3)
        correction = provider.calls[2]["messages"][-1]
        self.assertEqual(correction["note"], "Fix rejected candidates")
        self.assertIn("Made Up Fund", correction["content"])
        self.assertIn("home page", correction["content"])
        self.assertEqual(sorted(Lead.objects.values_list("dedupe_key", flat=True)), ["acme foundation", "bolt giving"])
        self.assertEqual(run.result, "Inserted 2. Skipped: 2 not in sources, 1 home page.")

    def test_no_correction_without_steps_to_spare(self, search):
        run = make_run(make_config(max_iterations=3))
        made_up = {**FUNDERS[0], "org_name": "Made Up Fund", "application_url": "https://made.up/grants"}

        run_agent(run, FakeProvider(tool_call(), answer([made_up])))

        self.assertEqual(run.status, AgentRun.Status.DONE)
        self.assertEqual(run.result, "Inserted 0. Skipped: 1 not in sources.")

    def test_provider_error_fails_the_run_and_keeps_history(self, search):
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
    def test_missing_provider_key_fails_the_run(self, search):
        provider = make_provider(secret_env="HLAGENTS_TEST_UNSET_KEY")
        run = make_run(make_config(provider=provider))

        run_agent(run)

        self.assertEqual(run.status, AgentRun.Status.FAILED)
        self.assertEqual(run.error, f"HLAGENTS_TEST_UNSET_KEY isn't set, so {provider} can't be used.")


@mock.patch("hlagents.tools.web_search.search", return_value=(SEARCH_RESULTS, ""))
class CostCapTest(TestCase):
    def setUp(self):
        self.limits = AgentLimits.get()
        self.limits.tool_costs = {"web_search": "0.01"}
        self.limits.save()
        # $1 per million input tokens, $2 per million output tokens
        self.config = make_config(provider=make_provider(input_cost_per_mtok=1, output_cost_per_mtok=2))

    def test_cost_counts_tokens_and_tool_calls(self, search):
        self.limits.run_cost_cap = Decimal("5.00")
        self.limits.save()
        run = make_run(self.config)
        run_agent(run, FakeProvider(tool_call(tokens=(1_000_000, 0)), answer([], tokens=(0, 500_000))))
        # $1 input + $1 output + $0.01 search
        self.assertEqual(run.cost, Decimal("2.01"))

    def test_stops_at_the_run_cap(self, search):
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

    def test_stops_at_the_daily_cap(self, search):
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
        result = services.save_leads(first, cite(first, FUNDERS + [{"org_name": "ACME foundation"}]))
        self.assertEqual((result.inserted, result.skipped), (2, {"already known": 1}))

        second = make_run()
        more = cite(second, [{**FUNDERS[1], "org_name": "Bolt Giving"}, {**FUNDERS[0], "org_name": "Cora Fund"}])
        result = services.save_leads(second, more)
        self.assertEqual((result.inserted, result.skipped), (1, {"already known": 1}))
        self.assertEqual(Lead.objects.get(dedupe_key="cora fund").source_run, second)

    def test_rejected_leads_still_block_duplicates(self):
        run = make_run()
        services.save_leads(run, cite(run, FUNDERS[:1]))
        Lead.objects.update(review_status=Lead.ReviewStatus.REJECTED)
        run = make_run()
        self.assertEqual(services.save_leads(run, cite(run, FUNDERS[:1])).skipped, {"already known": 1})

    def test_same_key_in_another_kind_is_not_a_duplicate(self):
        Lead.objects.create(kind=Lead.Kind.OUTREACH, dedupe_key="acme foundation")
        run = make_run()
        self.assertEqual(services.save_leads(run, cite(run, FUNDERS[:1])).inserted, 1)

    def test_funding_urls_must_be_in_sources_and_not_home_pages(self):
        run = make_run()
        cite(run, [{"url": "https://WWW.Acme.example.org/grants/?ref=x"}])
        candidates = [
            FUNDERS[0],
            {**FUNDERS[0], "org_name": "Home", "application_url": "https://acme.example.org/"},
            {**FUNDERS[0], "org_name": "None", "application_url": ""},
            {**FUNDERS[0], "org_name": "Elsewhere", "application_url": "https://acme.example.org/other"},
        ]
        result = services.save_leads(run, candidates)
        self.assertEqual((result.inserted, result.skipped), (1, {"home page": 2, "not in sources": 1}))
        self.assertEqual([reason for _, reason in result.rejected], ["home page", "home page", "not in sources"])

    def test_outreach_skips_missing_invalid_unsourced_and_shared_emails(self):
        run = make_run(make_config("outreach"))
        cite(run, [{"content": "Contact Pat at PAT@dav.org or info@dav.org"}])
        candidates = [
            {"first_name": "Pat", "org_name": "DAV", "contact_email": "Pat@DAV.org"},
            {"first_name": "Sam", "org_name": "VFW", "contact_email": ""},
            {"first_name": "Lee", "org_name": "VVA", "contact_email": "not an email"},
            {"first_name": "Pat", "org_name": "DAV", "contact_email": "pat@dav.org"},
            {"first_name": "Kim", "org_name": "DAV", "contact_email": "kim@dav.org"},
            {"first_name": "", "org_name": "DAV", "contact_email": "info@dav.org"},
        ]
        result = services.save_leads(run, candidates)
        self.assertEqual(
            (result.inserted, result.skipped),
            (1, {"incomplete": 2, "already known": 1, "not in sources": 1, "shared mailbox": 1}),
        )
        lead = Lead.objects.get()
        self.assertEqual((lead.kind, lead.contact_email, lead.first_name), ("outreach", "pat@dav.org", "Pat"))

    def test_long_values_are_truncated(self):
        run = make_run()
        services.save_leads(run, cite(run, [{**FUNDERS[0], "org_name": "x" * 300, "funding_amount": "9" * 200}]))
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
        self.assertEqual(run.messages[0]["role"], "system")
        self.assertRegex(run.messages[0]["content"], r"^You find things.\n\nToday is \w+ \d+, \d{4}\.$")
        self.assertEqual(run.messages[1:], [{"role": "user", "content": "Only foundations in Texas."}])

    def test_tells_the_agent_which_leads_are_known(self):
        Lead.objects.create(kind=Lead.Kind.FUNDING, org_name="Acme Foundation", dedupe_key="acme foundation")
        Lead.objects.create(kind=Lead.Kind.FUNDING, org_name="Bolt Giving", dedupe_key="bolt giving",
                            review_status=Lead.ReviewStatus.REJECTED)
        Lead.objects.create(kind=Lead.Kind.OUTREACH, org_name="DAV", contact_email="pat@dav.org", dedupe_key="pat@dav.org")

        note = make_run().messages[2]

        self.assertEqual(note["note"], "Already known")
        self.assertEqual(note["content"], "We already know these funders. Don't return them again:\n- Bolt Giving\n- Acme Foundation")

    def test_outreach_known_leads_list_emails(self):
        Lead.objects.create(kind=Lead.Kind.OUTREACH, contact_email="x@vso.org", dedupe_key="x@vso.org")
        Lead.objects.create(kind=Lead.Kind.OUTREACH, first_name="Pat", last_name="Rivera", org_name="DAV",
                            contact_email="pat@dav.org", dedupe_key="pat@dav.org")
        self.assertEqual(
            services.known_leads_hint(Lead.Kind.OUTREACH),
            "We already know these people. Don't return them again:\n- pat@dav.org (Pat Rivera, DAV)\n- x@vso.org",
        )

    def test_no_known_leads_no_note(self):
        self.assertEqual(len(make_run().messages), 2)
