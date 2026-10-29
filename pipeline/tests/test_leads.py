"""Lead flows: Funding and Outreach hold hlagents leads, not people
(docs/designs/completed/hlagents.md §3.6)."""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from hlagents.models import Lead
from pipeline import dashboard, services
from pipeline.models import Activity, Enrollment, Flow, Step

from .test_actions import events
from .test_dashboard import person

URL = reverse("staff")


class LeadFlowTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("staff@example.com", is_staff=True, first_name="Sam", last_name="Staff")
        cls.funding = Flow.objects.get(slug="funding")
        cls.job_search = Flow.objects.get(slug="resume-job-search")
        cls.found, cls.researching = Step.objects.filter(phase__flow=cls.funding)[:2]
        cls.acme = Lead.objects.create(kind="funding", dedupe_key="acme foundation", org_name="Acme Foundation")
        cls.vet = person("vet@example.com", "Pat", "Vet")

    def setUp(self):
        self.client.force_login(self.staff)
        self.enrollment = services.enroll(None, self.funding, self.staff, lead=self.acme)
        self.person_enrollment = services.enroll(self.vet, self.job_search, None)


class EnrollLeadTest(LeadFlowTestCase):
    def test_enrolled_and_logged_on_the_lead(self):
        self.assertEqual((self.enrollment.lead, self.enrollment.person, self.enrollment.current_step), (self.acme, None, self.found))
        self.assertEqual(self.enrollment.label, "Acme Foundation")
        self.assertEqual(self.acme.activities.get(kind=Activity.Kind.ENROLLED).to_value, "Found")

    def test_one_open_enrollment_per_flow(self):
        with self.assertRaises(services.AlreadyEnrolled):
            services.enroll(None, self.funding, self.staff, lead=self.acme)

    def test_subject_must_match_the_flow(self):
        with self.assertRaisesMessage(ValidationError, "Funding is for leads"):
            services.enroll(self.vet, self.funding, self.staff)
        with self.assertRaisesMessage(ValidationError, "Resume & Job Search is for people"):
            services.enroll(None, self.job_search, self.staff, lead=self.acme)
        with self.assertRaisesMessage(ValidationError, "a person or a lead"):
            services.enroll(None, self.funding, self.staff)

    def test_constraint_needs_exactly_one_subject(self):
        for kwargs in ({}, {"person": self.vet, "lead": self.acme}):
            with self.subTest(kwargs=list(kwargs)), self.assertRaises(IntegrityError), transaction.atomic():
                Enrollment.objects.create(
                    flow=self.funding, current_step=self.found, step_entered_at=self.enrollment.step_entered_at, **kwargs
                )

    def test_moves_and_notes_go_on_the_lead_timeline(self):
        services.move_to_step(self.enrollment, self.researching, self.staff)
        services.add_note(None, self.staff, "Called them.", enrollment=self.enrollment, lead=self.acme)
        self.assertEqual(
            list(self.acme.activities.order_by("id").values_list("kind", flat=True)), ["enrolled", "step_change", "note"]
        )
        with self.assertRaisesMessage(ValidationError, "belongs to someone else"):
            services.add_note(self.vet, self.staff, "Wrong.", enrollment=self.enrollment)


class LeadDashboardTest(LeadFlowTestCase):
    def test_lead_flow_has_a_tab_table_and_board(self):
        self.assertIn(("funding", "Funding"), dashboard.tabs())
        response = self.client.get(URL, {"tab": "funding", "view": "table"})
        self.assertContains(response, "Acme Foundation")
        self.assertContains(response, self.acme.get_absolute_url())
        self.assertContains(response, "1 lead")
        self.assertNotContains(response, "vet@example.com")

        response = self.client.get(URL, {"tab": "funding", "view": "board"})
        self.assertContains(response, f'id="card-{self.enrollment.pk}"')
        self.assertContains(response, "Acme Foundation")

    def test_people_tabs_and_counts_leave_leads_out(self):
        for tab in ("all", "mine"):
            services.assign(self.enrollment, self.staff, self.staff)
            services.assign(self.person_enrollment, self.staff, self.staff)
            response = self.client.get(URL, {"tab": tab})
            with self.subTest(tab=tab):
                self.assertContains(response, "vet@example.com")
                self.assertNotContains(response, "Acme Foundation")
        unassigned = next(c for c in dashboard.header_counts() if c["label"] == "Unassigned")
        self.assertEqual(unassigned["count"], 0)

    def test_search_finds_leads_by_org(self):
        response = self.client.get(URL, {"tab": "funding", "view": "table", "q": "acme"})
        self.assertContains(response, "Acme Foundation")

    def test_last_activity_is_the_leads(self):
        row = dashboard.row(self.enrollment.pk, self.staff)
        self.assertIsNotNone(row.last_activity)
        self.assertEqual((row.enroll_choices, row.also_in), ([], []))

    def test_people_rows_cant_join_lead_flows(self):
        row = dashboard.row(self.person_enrollment.pk, self.staff)
        self.assertNotIn(self.funding, row.enroll_choices)
        response = self.client.post(reverse("pipeline:enroll", args=[self.person_enrollment.pk]), {"flows": [self.funding.pk]})
        self.assertIn("Choose at least one flow", events(response)["toast"]["text"])


class LeadActionTest(LeadFlowTestCase):
    def test_board_move_names_the_lead(self):
        response = self.client.post(
            reverse("pipeline:move", args=[self.enrollment.pk]),
            {"step": self.researching.pk, "from_step": self.found.pk, "render": "card"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(events(response)["toast"]["text"], "Moved Acme Foundation to Researching.")

    def test_note_on_a_lead_row(self):
        response = self.client.post(reverse("pipeline:note", args=[self.enrollment.pk]), {"text": "Emailed.", "kind": "email"})
        self.assertEqual(events(response)["toast"]["text"], "Note added.")
        self.assertTrue(self.acme.activities.filter(kind="email", enrollment=self.enrollment).exists())

    def test_leads_cant_enroll_in_more_flows(self):
        response = self.client.post(reverse("pipeline:enroll", args=[self.enrollment.pk]), {"flows": [self.job_search.pk]})
        self.assertIn("join their flow when they're approved", events(response)["toast"]["text"])
