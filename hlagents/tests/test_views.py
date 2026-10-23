from unittest import mock

from django.contrib.auth.models import Group, Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from background_tasks.models import Task
from background_tasks.queue import TASK_ID_HEADER
from hlagents import services
from hlagents.models import AgentConfig, AgentRun, Lead
from hlagents.tests.fakes import make_config, make_run
from pipeline.models import Step


class ViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agent_user = User.objects.create_user("sam@example.com", "sam@example.com", "pw", is_staff=True)
        cls.agent_user.groups.add(Group.objects.get(name="Agents"))
        cls.other_staff = User.objects.create_user("kim@example.com", "kim@example.com", "pw", is_staff=True)
        cls.config = make_config()

    def setUp(self):
        self.client.force_login(self.agent_user)


class PermissionTest(ViewTestCase):
    def test_anonymous_goes_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("hlagents:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_staff_without_the_permission_get_403(self):
        self.client.force_login(self.other_staff)
        for url in (reverse("hlagents:index"), reverse("hlagents:leads")):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_agents_group_has_access_and_a_nav_link(self):
        response = self.client.get(reverse("hlagents:index"))
        self.assertContains(response, self.config.name)
        self.assertContains(response, f'href="{reverse("hlagents:index")}"')

    def test_view_only_user_cant_run_review_or_import(self):
        viewer = User.objects.create_user("vi@example.com", "vi@example.com", "pw")
        viewer.user_permissions.add(*Group.objects.get(name="Agents").permissions.filter(codename__startswith="view_"))
        self.client.force_login(viewer)
        lead = Lead.objects.create(kind="funding", dedupe_key="acme", org_name="Acme")

        self.assertNotContains(self.client.get(reverse("hlagents:index")), ">Run</button>")
        self.assertEqual(self.client.post(reverse("hlagents:start_run", args=[self.config.pk]), {}).status_code, 403)
        self.assertEqual(self.client.post(reverse("hlagents:review", args=[lead.pk]), {"status": "approved"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("hlagents:lead", args=[lead.pk]), {"org_name": "X"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("hlagents:import")).status_code, 403)

    def test_agents_group_permissions(self):
        perms = set(Group.objects.get(name="Agents").permissions.values_list("codename", flat=True))
        self.assertEqual(perms, {"view_agentconfig", "view_agentrun", "add_agentrun", "view_lead", "change_lead", "add_lead"})


class StartRunTest(ViewTestCase):
    @mock.patch("hlagents.services.queue_task")
    def test_creates_and_queues_a_run(self, queue_task):
        queue_task.return_value = Task.objects.create(target_path="/", payload={})
        response = self.client.post(
            reverse("hlagents:start_run", args=[self.config.pk]), {f"agent-{self.config.pk}-request": "Only Texas."}
        )

        run = AgentRun.objects.get()
        self.assertRedirects(response, reverse("hlagents:run", args=[run.pk]))
        self.assertEqual(
            (run.started_by, run.messages[1]["content"], run.task),
            (self.agent_user, "Only Texas.", queue_task.return_value),
        )
        queue_task.assert_called_once_with(reverse("hlagents:task_run_agent"), {"run_id": run.pk})

    @mock.patch("hlagents.services.queue_task")
    def test_empty_request_is_refused(self, queue_task):
        response = self.client.post(
            reverse("hlagents:start_run", args=[self.config.pk]), {f"agent-{self.config.pk}-request": ""}
        )
        self.assertRedirects(response, reverse("hlagents:index"))
        self.assertFalse(AgentRun.objects.exists())

    def test_inactive_agent_is_404(self):
        AgentConfig.objects.filter(pk=self.config.pk).update(active=False)
        response = self.client.post(
            reverse("hlagents:start_run", args=[self.config.pk]), {f"agent-{self.config.pk}-request": "x"}
        )
        self.assertEqual(response.status_code, 404)


class RunPageTest(ViewTestCase):
    def test_queued_run_polls(self):
        run = make_run(self.config)
        response = self.client.get(reverse("hlagents:run", args=[run.pk]))
        self.assertContains(response, f'hx-get="{reverse("hlagents:run_status", args=[run.pk])}"')
        self.assertContains(response, "Find 2 things.")

    def test_finished_run_shows_result_and_leads_without_polling(self):
        run = make_run(self.config)
        run.status = AgentRun.Status.DONE
        run.result = "Inserted 1, skipped 0 (duplicate or incomplete)."
        run.messages += [{"role": "assistant", "content": "[]"}]
        run.save()
        Lead.objects.create(kind="funding", dedupe_key="acme", org_name="Acme Foundation", source_run=run)

        response = self.client.get(reverse("hlagents:run_status", args=[run.pk]))

        self.assertNotContains(response, "hx-trigger")
        self.assertContains(response, "Inserted 1")
        self.assertContains(response, "Acme Foundation")


class LeadViewsTest(ViewTestCase):
    def setUp(self):
        super().setUp()
        self.lead = Lead.objects.create(kind="funding", dedupe_key="acme foundation", org_name="Acme Foundation")

    def test_review_returns_the_row(self):
        response = self.client.post(
            reverse("hlagents:review", args=[self.lead.pk]), {"status": "approved"}, HTTP_HX_REQUEST="true"
        )
        self.assertContains(response, f'id="lead-{self.lead.pk}"')
        self.assertContains(response, "Approved")
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.review_status, "approved")

    def test_bad_review_status_is_400(self):
        response = self.client.post(reverse("hlagents:review", args=[self.lead.pk]), {"status": "maybe"})
        self.assertEqual(response.status_code, 400)

    def test_edit_saves_and_shows_the_timeline(self):
        response = self.client.post(reverse("hlagents:lead", args=[self.lead.pk]), {"org_name": "Acme Fund", "url": ""})
        self.assertRedirects(response, reverse("hlagents:lead", args=[self.lead.pk]))
        response = self.client.get(reverse("hlagents:lead", args=[self.lead.pk]))
        self.assertContains(response, "Organization: Acme Foundation → Acme Fund")

    def test_duplicate_edit_shows_the_error(self):
        Lead.objects.create(kind="funding", dedupe_key="bolt", org_name="Bolt")
        response = self.client.post(reverse("hlagents:lead", args=[self.lead.pk]), {"org_name": "BOLT"})
        self.assertContains(response, "Another lead already has this.")
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.org_name, "Acme Foundation")

    def test_outreach_form_has_outreach_fields(self):
        lead = Lead.objects.create(kind="outreach", dedupe_key="pat@dav.org", contact_email="pat@dav.org")
        response = self.client.get(reverse("hlagents:lead", args=[lead.pk]))
        self.assertContains(response, 'name="contact_email"')
        self.assertNotContains(response, 'name="funding_amount"')

    def test_opt_out(self):
        response = self.client.post(reverse("hlagents:opt_out", args=[self.lead.pk]), {"opted_out": "1"})
        self.assertRedirects(response, reverse("hlagents:lead", args=[self.lead.pk]))
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.opted_out_at)

    def test_leads_list_filters(self):
        Lead.objects.create(kind="outreach", dedupe_key="pat@dav.org", contact_email="pat@dav.org", org_name="DAV")
        response = self.client.get(reverse("hlagents:leads"), {"kind": "outreach"})
        self.assertContains(response, "pat@dav.org")
        self.assertNotContains(response, "Acme Foundation")
        response = self.client.get(reverse("hlagents:leads"), {"q": "acme"})
        self.assertContains(response, "Acme Foundation")
        self.assertNotContains(response, "pat@dav.org")


class StageViewTest(ViewTestCase):
    def setUp(self):
        super().setUp()
        self.lead = Lead.objects.create(kind="funding", dedupe_key="acme foundation", org_name="Acme Foundation")
        services.review(self.lead, Lead.ReviewStatus.APPROVED, self.agent_user)
        self.found = Step.objects.get(phase__flow__slug="funding", title="Found")
        self.applying = Step.objects.get(phase__flow__slug="funding", title="Applying")

    def move(self, step, from_step=None, **headers):
        data = {"step": step.pk, "from_step": (from_step or self.found).pk}
        return self.client.post(reverse("hlagents:stage", args=[self.lead.pk]), data, **headers)

    def test_htmx_move_returns_the_row(self):
        response = self.move(self.applying, HTTP_HX_REQUEST="true")
        self.assertContains(response, f'id="lead-{self.lead.pk}"')
        self.assertContains(response, f'<option value="{self.applying.pk}" selected>')
        self.assertEqual(services.open_enrollment(self.lead).current_step, self.applying)

    def test_stale_move_shows_the_saved_stage(self):
        self.move(self.applying)
        submitted = Step.objects.get(phase__flow__slug="funding", title="Submitted")
        response = self.move(submitted, HTTP_HX_REQUEST="true")
        self.assertContains(response, "no longer on Found")
        self.assertContains(response, f'<option value="{self.applying.pk}" selected>')

    def test_form_move_redirects_to_the_lead(self):
        response = self.move(self.applying)
        self.assertRedirects(response, reverse("hlagents:lead", args=[self.lead.pk]))
        response = self.client.get(reverse("hlagents:lead", args=[self.lead.pk]))
        self.assertContains(response, "Found → Applying")
        self.assertContains(response, "View on the Funding board")

    def test_needs_change_lead(self):
        viewer = User.objects.create_user("viewer@example.com", "viewer@example.com", "pw")
        viewer.user_permissions.add(Permission.objects.get(codename="view_lead"))
        self.client.force_login(viewer)
        response = self.move(self.applying)
        self.assertIn(response.status_code, (302, 403))
        self.assertEqual(services.open_enrollment(self.lead).current_step, self.found)

    def test_untracked_lead_explains(self):
        lead = Lead.objects.create(kind="funding", dedupe_key="bolt", org_name="Bolt")
        response = self.client.get(reverse("hlagents:lead", args=[lead.pk]))
        self.assertContains(response, "Approve this lead to track its stage")

    def test_leads_list_shows_and_filters_by_stage(self):
        Lead.objects.create(kind="funding", dedupe_key="bolt", org_name="Bolt")
        self.move(self.applying)
        response = self.client.get(reverse("hlagents:leads"), {"stage": "Applying"})
        self.assertContains(response, "Acme Foundation")
        self.assertNotContains(response, "Bolt")
        response = self.client.get(reverse("hlagents:leads"))
        self.assertContains(response, "Not tracked")

    def test_leads_list_queries_dont_grow_with_leads(self):
        def count():
            with CaptureQueriesContext(connection) as queries:
                self.client.get(reverse("hlagents:leads"))
            return len(queries)

        before = count()
        for i in range(5):
            lead = Lead.objects.create(kind="funding", dedupe_key=f"fund {i}", org_name=f"Fund {i}")
            services.review(lead, Lead.ReviewStatus.APPROVED, self.agent_user)
        self.assertEqual(count(), before)


class ImportViewTest(ViewTestCase):
    def upload(self, text):
        return self.client.post(
            reverse("hlagents:import"), {"file": SimpleUploadedFile("partners.csv", text.encode(), "text/csv")}
        )

    def test_import(self):
        response = self.upload("EMAIL,Status\npat@dav.org,\nlee@vfw.org,Bounced #2\n")
        self.assertRedirects(response, reverse("hlagents:leads") + "?kind=outreach&source=import")
        self.assertEqual(Lead.objects.filter(source="import").count(), 2)

    def test_bad_rows_import_nothing(self):
        response = self.upload("EMAIL,Status\npat@dav.org,\nlee@vfw.org,Unsubscribed\n")
        self.assertContains(response, "Row 3: unknown Status")
        self.assertFalse(Lead.objects.exists())


class TaskEndpointTest(TestCase):
    def post(self, run):
        task = Task.objects.create(target_path=reverse("hlagents:task_run_agent"), payload={"run_id": run.pk})
        return self.client.post(reverse("hlagents:task_run_agent"), headers={TASK_ID_HEADER: str(task.pk)})

    @mock.patch("hlagents.tasks.run_agent")
    def test_runs_a_queued_run(self, run_agent):
        run = make_run()
        run_agent.side_effect = lambda r: r
        response = self.post(run)
        self.assertEqual(response.json(), {"status": "success"})
        run_agent.assert_called_once()
        run.refresh_from_db()
        self.assertEqual(run.status, AgentRun.Status.RUNNING)

    @mock.patch("hlagents.tasks.run_agent")
    def test_a_started_run_is_not_run_again(self, run_agent):
        run = make_run()
        AgentRun.objects.filter(pk=run.pk).update(status=AgentRun.Status.RUNNING)
        response = self.post(run)
        self.assertEqual(response.status_code, 200)
        run_agent.assert_not_called()
        self.assertEqual(Task.objects.get().result, "skipped (running)")
