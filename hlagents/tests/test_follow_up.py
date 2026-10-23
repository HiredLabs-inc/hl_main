from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from background_tasks.models import Task
from hlagents import services
from hlagents.loop import run_agent
from hlagents.models import AgentLimits, AgentRun, Lead
from hlagents.tests.fakes import FUNDERS, FakeProvider, answer, make_config, make_provider, make_run

MORE_FUNDERS = [{**FUNDERS[0], "org_name": "Texas Fund"}]


def finished_run(**kwargs):
    run = make_run(**kwargs)
    run_agent(run, FakeProvider(answer(FUNDERS)))
    return run


@mock.patch("hlagents.services.queue_task", side_effect=lambda *args: Task.objects.create(target_path="/", payload={}))
class FollowUpTest(TestCase):
    def test_appends_the_message_and_queues_the_run(self, queue_task):
        run = finished_run()

        services.follow_up(run, "  Only Texas.  ")

        run.refresh_from_db()
        self.assertEqual((run.status, run.result, run.error), (AgentRun.Status.QUEUED, "", ""))
        self.assertEqual(run.messages[-1], {"role": "user", "content": "Only Texas."})
        queue_task.assert_called_once_with(reverse("hlagents:task_run_agent"), {"run_id": run.pk})
        self.assertEqual(run.task, Task.objects.get())

    def test_continuing_adds_leads_to_the_same_run(self, queue_task):
        run = finished_run()
        services.follow_up(run, "Find more.")
        provider = FakeProvider(answer(FUNDERS + MORE_FUNDERS))

        run_agent(AgentRun.objects.get(pk=run.pk), provider)

        run.refresh_from_db()
        self.assertEqual(run.status, AgentRun.Status.DONE)
        self.assertEqual(run.result, "Inserted 1, skipped 2 (duplicate or incomplete).")
        self.assertEqual(run.leads.count(), 3)
        # The model saw the whole conversation, ending with the follow-up
        sent = provider.calls[0]["messages"]
        self.assertEqual([m["role"] for m in sent], ["system", "user", "assistant", "user"])
        self.assertEqual(run.iterations, 2)

    def test_a_failed_run_can_be_followed_up(self, queue_task):
        run = make_run()
        run_agent(run, FakeProvider(answer("Here you go: nothing")))
        self.assertEqual(run.status, AgentRun.Status.FAILED)
        services.follow_up(run, "Return only the JSON.")
        run.refresh_from_db()
        self.assertEqual(run.status, AgentRun.Status.QUEUED)

    def test_refused_while_in_progress_or_empty(self, queue_task):
        run = make_run()
        with self.assertRaisesMessage(ValidationError, "still working"):
            services.follow_up(run, "More.")
        with self.assertRaisesMessage(ValidationError, "can't be empty"):
            services.follow_up(finished_run(), " ")
        queue_task.assert_not_called()

    def test_refused_at_the_run_cap(self, queue_task):
        run = finished_run()
        AgentRun.objects.filter(pk=run.pk).update(cost=Decimal("1.00"))
        run.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "reached the $1.00 run cap"):
            services.follow_up(run, "More.")

        # Raising the cap lets it continue
        AgentLimits.objects.filter(pk=1).update(run_cost_cap=Decimal("2.00"))
        services.follow_up(run, "More.")

    def test_refused_when_the_provider_is_turned_off(self, queue_task):
        run = finished_run()
        run.provider.active = False
        run.provider.save()
        with self.assertRaisesMessage(ValidationError, "is turned off in settings"):
            services.follow_up(run, "More.")


@mock.patch("hlagents.services.queue_task", side_effect=lambda *args: Task.objects.create(target_path="/", payload={}))
class StartRunChecksTest(TestCase):
    def test_refused_at_the_daily_cap(self, queue_task):
        run = make_run()
        AgentRun.objects.filter(pk=run.pk).update(cost=Decimal("10.00"))
        with self.assertRaisesMessage(ValidationError, "daily cap"):
            services.start_run(make_config(), None)

    @override_settings(HLAGENTS_PROVIDER_SECRETS=["HLAGENTS_TEST_UNSET_KEY"])
    def test_refused_without_a_key(self, queue_task):
        config = make_config(provider=make_provider(secret_env="HLAGENTS_TEST_UNSET_KEY"))
        with self.assertRaisesMessage(ValidationError, "HLAGENTS_TEST_UNSET_KEY isn't set"):
            services.start_run(config, None)
        self.assertFalse(AgentRun.objects.exists())


@mock.patch("hlagents.services.queue_task", side_effect=lambda *args: Task.objects.create(target_path="/", payload={}))
class FollowUpViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("sam@example.com", "sam@example.com", "pw", is_staff=True)
        cls.user.groups.add(Group.objects.get(name="Agents"))

    def setUp(self):
        self.client.force_login(self.user)

    def test_form_shows_on_a_finished_run_and_queues_it(self, queue_task):
        run = finished_run()
        page = self.client.get(reverse("hlagents:run", args=[run.pk]))
        self.assertContains(page, f'action="{reverse("hlagents:follow_up", args=[run.pk])}"')

        response = self.client.post(reverse("hlagents:follow_up", args=[run.pk]), {"message": "Only Texas."})

        self.assertRedirects(response, reverse("hlagents:run", args=[run.pk]))
        page = self.client.get(reverse("hlagents:run", args=[run.pk]))
        self.assertContains(page, "Follow-up")
        self.assertContains(page, "Only Texas.")
        self.assertNotContains(page, 'name="message"')

    def test_capped_run_says_why_instead_of_a_form(self, queue_task):
        run = finished_run()
        AgentRun.objects.filter(pk=run.pk).update(cost=Decimal("5"))
        page = self.client.get(reverse("hlagents:run", args=[run.pk]))
        self.assertContains(page, "Follow-ups are off: This run has reached the $1.00 run cap.")
        self.assertNotContains(page, 'name="message"')

    def test_refusal_is_shown_as_a_message(self, queue_task):
        run = make_run()
        response = self.client.post(reverse("hlagents:follow_up", args=[run.pk]), {"message": "More."}, follow=True)
        self.assertContains(response, "still working")
        self.assertEqual(Lead.objects.count(), 0)

    def test_view_only_user_cant_follow_up(self, queue_task):
        viewer = User.objects.create_user("vi@example.com", "vi@example.com", "pw")
        viewer.user_permissions.add(*Group.objects.get(name="Agents").permissions.filter(codename__startswith="view_"))
        self.client.force_login(viewer)
        run = finished_run()
        self.assertNotContains(self.client.get(reverse("hlagents:run", args=[run.pk])), 'name="message"')
        self.assertEqual(self.client.post(reverse("hlagents:follow_up", args=[run.pk]), {"message": "x"}).status_code, 403)
