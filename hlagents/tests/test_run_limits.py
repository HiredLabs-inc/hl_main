"""Run time limits, Stop and stuck runs (docs/gcp-agents.md §3.7)."""
import json
import time
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from background_tasks.models import Task
from hlagents import services
from hlagents.loop import TOOL_STOPPED, run_agent
from hlagents.models import AgentRun, Lead
from hlagents.providers import ProviderError, call_with_limit
from hlagents.tasks import run_agent_task
from hlagents.tests.fakes import FUNDERS, FakeProvider, answer, make_config, make_provider, make_run, tool_call
from hlagents.tests.test_gemini import function_call, gemini_response
from hlagents.tests.test_loop import SEARCH_RESULTS


class SlowProvider(FakeProvider):
    def __init__(self, seconds, *replies):
        super().__init__(*replies)
        self.seconds = seconds

    def chat(self, *args, **kwargs):
        time.sleep(self.seconds)
        return super().chat(*args, **kwargs)


def press_stop(run):
    AgentRun.objects.filter(pk=run.pk).update(stop_requested=True)


class CallWithLimitTest(TestCase):
    def test_returns_a_fast_reply(self):
        self.assertEqual(call_with_limit(lambda: "hi", 5), "hi")

    def test_raises_at_the_limit_without_waiting_for_the_call(self):
        started = time.monotonic()
        with self.assertRaisesMessage(ProviderError, "gemini-test didn't answer within 0.1 s."):
            call_with_limit(lambda: time.sleep(1), 0.1, "gemini-test")
        self.assertLess(time.monotonic() - started, 0.5)

    def test_the_calls_own_errors_pass_through(self):
        with self.assertRaises(ConnectionError):
            call_with_limit(lambda: (_ for _ in ()).throw(ConnectionError("down")), 5)


@mock.patch("hlagents.tools.web_search.search", return_value=(SEARCH_RESULTS, ""))
class TimeLimitTest(TestCase):
    @override_settings(HLAGENTS_CALL_TIME_LIMIT=0.1)
    def test_a_slow_call_fails_the_run_and_it_can_take_a_follow_up(self, search):
        run = make_run()
        run_agent(run, SlowProvider(1, answer([])))

        run.refresh_from_db()
        self.assertEqual(run.status, AgentRun.Status.FAILED)
        self.assertEqual(run.error, "test-model didn't answer within 0.1 s.")
        self.assertEqual(services.follow_up_problem(run), "")

    @override_settings(HLAGENTS_CALL_TIME_LIMIT=120, HLAGENTS_RUN_TIME_LIMIT=30)
    def test_the_call_limit_is_the_time_left_in_the_run(self, search):
        with mock.patch("hlagents.loop.call_with_limit", side_effect=lambda func, seconds, model: func()) as limit:
            run_agent(make_run(), FakeProvider(answer([])))
        seconds = limit.call_args.args[1]
        self.assertTrue(29 < seconds <= 30, seconds)

    @override_settings(HLAGENTS_CALL_TIME_LIMIT=5)
    def test_the_call_limit_applies_when_the_run_has_more_time(self, search):
        with mock.patch("hlagents.loop.call_with_limit", side_effect=lambda func, seconds, model: func()) as limit:
            run_agent(make_run(), FakeProvider(answer([])))
        self.assertEqual(limit.call_args.args[1], 5)


@mock.patch("hlagents.tools.web_search.search", return_value=(SEARCH_RESULTS, ""))
class StopTest(TestCase):
    def test_stopping_a_queued_run_stops_it_and_the_worker_skips_it(self, search):
        run = make_run()
        services.stop_run(run)

        run.refresh_from_db()
        self.assertEqual((run.status, run.error), (AgentRun.Status.STOPPED, services.STOPPED_BY_STAFF))
        self.assertEqual(run_agent_task(run.pk), "skipped (stopped)")

    def test_a_run_stops_before_its_next_step(self, search):
        run = make_run()
        # Staff press Stop while the search runs; the loop saves after it
        search.side_effect = lambda query, max_results: press_stop(run) or (SEARCH_RESULTS, "")
        provider = FakeProvider(tool_call(), answer(FUNDERS))

        run_agent(run, provider)

        run.refresh_from_db()
        self.assertEqual((run.status, run.error), (AgentRun.Status.STOPPED, services.STOPPED_BY_STAFF))
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(run.messages[-1]["role"], "tool")

    def test_a_run_stops_before_its_next_tool_call_and_every_call_gets_a_reply(self, search):
        run = make_run()
        two_calls = tool_call()
        two_calls.message["tool_calls"].append({"function": {"name": "web_search", "arguments": {"query": "more"}}})
        search.side_effect = lambda query, max_results: press_stop(run) or (SEARCH_RESULTS, "")

        run_agent(run, FakeProvider(two_calls))

        run.refresh_from_db()
        self.assertEqual(run.status, AgentRun.Status.STOPPED)
        self.assertEqual(search.call_count, 1)
        replies = [json.loads(m["content"]) for m in run.messages if m["role"] == "tool"]
        self.assertEqual(replies[1], {"error": TOOL_STOPPED})
        self.assertEqual(run.tool_calls, 1)

    def test_a_stopped_run_keeps_its_leads_and_can_take_a_follow_up(self, search):
        run = make_run()
        # Rejected candidates are sent back to be fixed; Stop is pressed meanwhile
        provider = FakeProvider(
            tool_call(),
            answer(FUNDERS + [{**FUNDERS[0], "org_name": "Made Up", "application_url": "https://madeup.example.org/x"}]),
        )
        save_leads = services.save_leads

        def save_then_stop(*args):
            # Not inside chat(): provider calls run in a thread with its own connection
            result = save_leads(*args)
            press_stop(run)
            return result

        with mock.patch("hlagents.loop.services.save_leads", side_effect=save_then_stop):
            run_agent(run, provider)

        run.refresh_from_db()
        self.assertEqual(run.status, AgentRun.Status.STOPPED)
        self.assertEqual(Lead.objects.filter(source_run=run).count(), 2)
        self.assertEqual(run.result, "Inserted 2. Skipped: 1 not in sources.")
        self.assertEqual(services.follow_up_problem(run), "")

        with mock.patch("hlagents.services.queue_task", side_effect=lambda *args: Task.objects.create(target_path="/", payload={})):
            services.follow_up(run, "Find 2 more.")
        run.refresh_from_db()
        self.assertFalse(run.stop_requested)
        self.assertEqual(run.status, AgentRun.Status.QUEUED)


@override_settings(HLAGENTS_STALE_RUN_AFTER=900)
class StaleRunTest(TestCase):
    def test_a_running_run_not_saved_for_the_worker_timeout_is_failed(self):
        stuck, live = make_run(), make_run()
        AgentRun.objects.filter(pk=stuck.pk).update(status="running", updated_at=timezone.now() - timedelta(seconds=901))
        AgentRun.objects.filter(pk=live.pk).update(status="running", updated_at=timezone.now() - timedelta(seconds=600))

        self.assertEqual(services.fail_stale_runs(), 1)

        stuck.refresh_from_db()
        live.refresh_from_db()
        self.assertEqual((stuck.status, stuck.error), (AgentRun.Status.FAILED, services.WORKER_DIED))
        self.assertEqual(live.status, AgentRun.Status.RUNNING)
        self.assertFalse(stuck.in_progress())


class StopViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agent_user = User.objects.create_user("sam@example.com", "sam@example.com", "pw", is_staff=True)
        cls.agent_user.groups.add(Group.objects.get(name="Agents"))
        cls.viewer = User.objects.create_user("vi@example.com", "vi@example.com", "pw")
        cls.viewer.user_permissions.add(*Group.objects.get(name="Agents").permissions.filter(codename__startswith="view_"))

    def setUp(self):
        self.run = make_run()
        AgentRun.objects.filter(pk=self.run.pk).update(status="running")

    def test_staff_see_stop_and_pressing_it_asks_the_run_to_stop(self):
        self.client.force_login(self.agent_user)
        url = reverse("hlagents:run", args=[self.run.pk])
        self.assertContains(self.client.get(url), reverse("hlagents:stop", args=[self.run.pk]))

        response = self.client.post(reverse("hlagents:stop", args=[self.run.pk]))
        self.assertRedirects(response, url)
        self.run.refresh_from_db()
        self.assertTrue(self.run.stop_requested)
        self.assertEqual(self.run.status, AgentRun.Status.RUNNING)
        page = self.client.get(reverse("hlagents:run_status", args=[self.run.pk]))
        self.assertContains(page, "Stopping…")
        self.assertNotContains(page, reverse("hlagents:stop", args=[self.run.pk]))

    def test_view_only_user_cant_stop(self):
        self.client.force_login(self.viewer)
        self.assertNotContains(self.client.get(reverse("hlagents:run", args=[self.run.pk])), reverse("hlagents:stop", args=[self.run.pk]))
        self.assertEqual(self.client.post(reverse("hlagents:stop", args=[self.run.pk])).status_code, 403)
        self.run.refresh_from_db()
        self.assertFalse(self.run.stop_requested)

    def test_opening_a_stuck_run_marks_it_failed(self):
        AgentRun.objects.filter(pk=self.run.pk).update(updated_at=timezone.now() - timedelta(hours=1))
        self.client.force_login(self.agent_user)
        response = self.client.get(reverse("hlagents:run", args=[self.run.pk]))
        self.assertContains(response, services.WORKER_DIED)
        self.assertNotContains(response, reverse("hlagents:stop", args=[self.run.pk]))


@override_settings(GCP_PROJECT_ID="test-project", GEMINI_LOCATION="global")
@mock.patch("hlagents.tools.web_search.search", return_value=(SEARCH_RESULTS, ""))
@mock.patch("hlagents.providers.gemini.genai.Client")
class GeminiRunTest(TestCase):
    def test_a_funding_run_on_gemini_searches_and_saves_leads(self, client_class, search):
        generate = client_class.return_value.models.generate_content
        generate.side_effect = [
            gemini_response(parts=[function_call(signature=b"sig", query="veteran grants")]),
            gemini_response(text=json.dumps(FUNDERS)),
        ]
        run = make_run(make_config(provider=make_provider(kind="gemini")))

        run_agent(run)

        run.refresh_from_db()
        self.assertEqual((run.status, run.result), (AgentRun.Status.DONE, "Inserted 2."))
        search.assert_called_once_with("veteran grants", 8)
        # The second call sends the search back with its signature and reply
        contents = generate.call_args_list[1].kwargs["contents"]
        self.assertEqual([c.role for c in contents], ["user", "model", "user"])
        self.assertEqual(contents[1].parts[0].thought_signature, b"sig")
        self.assertEqual(contents[2].parts[0].function_response.name, "web_search")
        self.assertEqual(Lead.objects.filter(source_run=run).count(), 2)
