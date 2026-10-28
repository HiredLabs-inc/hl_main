from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase

from hlagents.completion import CompletionFailed, complete, complete_result
from hlagents.models import AgentLimits, AgentRun, TaskCall, TaskConfig, spent_today
from hlagents.providers import ChatResult, ProviderError
from hlagents.tests.fakes import FakeProvider, answer, make_provider, make_run


class CompleteTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("ada@example.com", "ada@example.com", "pw")
        cls.provider = make_provider(input_cost_per_mtok=Decimal("1.00"), output_cost_per_mtok=Decimal("2.00"))
        # 0008 seeds the task; point it at a test provider
        cls.task = TaskConfig.objects.get(key="resume_overview")
        cls.task.provider = cls.provider
        cls.task.model = "test-model"
        cls.task.instructions = "Write an overview."
        cls.task.options = {"temperature": 0.5}
        cls.task.save()

    def complete_with(self, *replies, **kwargs):
        provider = FakeProvider(*replies)
        with mock.patch("hlagents.completion.get_provider", return_value=provider) as get_provider:
            text = complete("resume_overview", "Job title: Welder", **kwargs)
        get_provider.assert_called_once_with(self.provider, timeout=45)
        return text, provider

    def test_sends_instructions_and_message_and_logs_the_call(self):
        text, provider = self.complete_with(answer("  An overview.  ", tokens=(200, 50)), user=self.user)

        self.assertEqual(text, "An overview.")
        self.assertEqual(
            provider.calls,
            [
                {
                    "model": "test-model",
                    "messages": [
                        {"role": "system", "content": "Write an overview."},
                        {"role": "user", "content": "Job title: Welder"},
                    ],
                    "tools": None,
                    "options": {"temperature": 0.5},
                }
            ],
        )
        call = TaskCall.objects.get()
        self.assertEqual((call.config, call.model, call.user, call.ok), (self.task, "test-model", self.user, True))
        self.assertEqual((call.input_tokens, call.output_tokens), (200, 50))
        # 200 × $1 + 50 × $2 per million tokens
        self.assertEqual(call.cost, Decimal("0.0003"))

    def test_anonymous_user_isnt_recorded(self):
        self.complete_with(answer("An overview."), user=AnonymousUser())
        self.assertIsNone(TaskCall.objects.get().user)

    def assert_fails_without_calling(self, reason):
        with mock.patch("hlagents.completion.get_provider") as get_provider:
            with self.assertRaises(CompletionFailed) as failed:
                complete("resume_overview", "Job title: Welder")
        get_provider.assert_not_called()
        self.assertEqual(failed.exception.model, "test-model")
        self.assertIn(reason, failed.exception.reason)
        call = TaskCall.objects.get()
        self.assertFalse(call.ok)
        self.assertIn(reason, call.error)

    def test_inactive_task(self):
        TaskConfig.objects.filter(pk=self.task.pk).update(active=False)
        self.assert_fails_without_calling("turned off")

    def test_inactive_provider(self):
        self.provider.active = False
        self.provider.save()
        self.assert_fails_without_calling("turned off")

    def test_daily_cap_counts_runs_and_task_calls(self):
        limits = AgentLimits.get()
        limits.daily_cost_cap = Decimal("0.05")
        limits.save()
        run = make_run()
        AgentRun.objects.filter(pk=run.pk).update(cost=Decimal("0.03"))
        TaskCall.objects.create(config=self.task, model="test-model", cost=Decimal("0.02"))
        self.assertEqual(spent_today(), Decimal("0.05"))

        TaskCall.objects.all().delete()
        TaskCall.objects.create(config=self.task, model="test-model", cost=Decimal("0.02"))
        with mock.patch("hlagents.completion.get_provider") as get_provider:
            with self.assertRaisesMessage(CompletionFailed, "daily cap"):
                complete("resume_overview", "Job title: Welder")
        get_provider.assert_not_called()

    def test_provider_error(self):
        with self.assertLogs("hlagents.completion", "ERROR"), self.assertRaises(CompletionFailed) as failed:
            self.complete_with(ProviderError("404 model not found"))
        self.assertEqual(failed.exception.model, "test-model")
        call = TaskCall.objects.get()
        self.assertFalse(call.ok)
        self.assertIn("404 model not found", call.error)

    def test_empty_reply(self):
        with self.assertRaisesMessage(CompletionFailed, "empty"):
            self.complete_with(answer("  "))
        self.assertFalse(TaskCall.objects.get().ok)

    def test_complete_result_returns_the_sources(self):
        reply = ChatResult(message={"role": "assistant", "content": " Found. "}, sources=[{"uri": "u"}], suggestions="<div/>")
        with mock.patch("hlagents.completion.get_provider", return_value=FakeProvider(reply)):
            result = complete_result("resume_overview", "q")
        self.assertEqual((result.message["content"], result.sources, result.suggestions), ("Found.", [{"uri": "u"}], "<div/>"))

    def test_complete_result_limits_the_call(self):
        with mock.patch("hlagents.completion.get_provider", return_value=FakeProvider(answer("Hi"))), \
                mock.patch("hlagents.completion.call_with_limit", side_effect=ProviderError("test-model didn't answer within 5 s.")) as limit:
            with self.assertRaisesMessage(CompletionFailed, "didn't answer within 5 s"):
                complete_result("resume_overview", "q", limit=5)
        self.assertEqual(limit.call_args.args[1:], (5, "test-model"))
        self.assertFalse(TaskCall.objects.get().ok)

    def test_unknown_task(self):
        with self.assertRaises(CompletionFailed) as failed:
            complete("no_such_task", "hi")
        self.assertEqual(failed.exception.model, "")
        self.assertFalse(TaskCall.objects.exists())
