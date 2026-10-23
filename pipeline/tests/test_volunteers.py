"""Volunteers on the lead flows: with work_lead_flows (the Agents group) they
see and work Funding and Outreach like staff, and nothing about people
(docs/volunteer-logins.md §3.3)."""
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from hlagents.models import Lead
from pipeline import dashboard, services
from pipeline.models import Enrollment, Flow, Step

from .test_actions import events
from .test_dashboard import person

URL = reverse("staff")


def volunteer(email="val@example.com", groups=("Agents",), **kwargs):
    user = User.objects.create_user(email, email, first_name=kwargs.pop("first_name", "Val"), **kwargs)
    user.groups.add(Group.objects.get(name="Volunteers"), *Group.objects.filter(name__in=groups))
    return user


class VolunteerLeadsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("staff@example.com", is_staff=True, first_name="Sam")
        cls.val = volunteer()
        cls.other = volunteer("vic@example.com", first_name="Vic")
        cls.funding = Flow.objects.get(slug="funding")
        cls.job_search = Flow.objects.get(slug="resume-job-search")
        cls.found = Step.objects.filter(phase__flow=cls.funding).first()
        cls.awarded = Step.objects.get(phase__flow=cls.funding, title="Awarded")
        cls.acme = Lead.objects.create(kind="funding", dedupe_key="acme foundation", org_name="Acme Foundation")
        cls.vet = person("vet@example.com", "Pat", "Vet")

    def setUp(self):
        self.client.force_login(self.val)
        self.lead_enrollment = services.enroll(None, self.funding, self.staff, lead=self.acme, assignee=self.other)
        self.person_enrollment = services.enroll(self.vet, self.job_search, None)

    def post(self, name, enrollment, data=None):
        return self.client.post(reverse(f"pipeline:{name}", args=[enrollment.pk]), data or {})


class DashboardTest(VolunteerLeadsTestCase):
    def test_only_the_lead_tabs(self):
        lead_tabs = [(flow.slug, flow.name) for flow in Flow.objects.filter(active=True, subject=Flow.Subject.LEAD)]
        self.assertEqual(dashboard.tabs(self.val), lead_tabs)
        self.assertIn(("intake", "Intake"), dashboard.tabs(self.staff))

    def test_opens_on_the_first_lead_tab(self):
        self.assertRedirects(self.client.get(URL), f"{URL}?tab={dashboard.tabs(self.val)[0][0]}")

    def test_sees_every_lead_enrollment_and_its_assignee(self):
        response = self.client.get(URL, {"tab": "funding", "view": "table"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row.pk for row in response.context["rows"]], [self.lead_enrollment.pk])
        self.assertContains(response, "Acme Foundation")
        self.assertContains(response, "Vic (volunteer)")
        self.assertNotContains(response, "count-strip")
        self.assertNotContains(response, "?tab=intake")

    def test_board(self):
        response = self.client.get(URL, {"tab": "funding", "view": "board"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acme Foundation")
        column = reverse("pipeline:board_column", args=["funding", self.found.pk])
        self.assertEqual(self.client.get(column).status_code, 200)
        person_step = Step.objects.filter(phase__flow=self.job_search).first()
        self.assertEqual(self.client.get(reverse("pipeline:board_column", args=[self.job_search.slug, person_step.pk])).status_code, 403)

    def test_people_tabs_and_counts_are_refused(self):
        for tab in ("intake", self.job_search.slug, dashboard.MINE, dashboard.ALL):
            with self.subTest(tab=tab):
                self.assertEqual(self.client.get(URL, {"tab": tab}).status_code, 403)
        self.assertEqual(self.client.get(URL, {"tab": "funding", "part": "counts"}).status_code, 403)
        self.assertEqual(self.client.get(URL, {"tab": "nope"}).status_code, 404)

    def test_needs_work_lead_flows(self):
        self.client.force_login(volunteer("nobody@example.com", groups=()))
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(self.client.get(URL, {"tab": "funding"}).status_code, 403)

    def test_staff_assignee_choices(self):
        self.client.force_login(self.staff)
        lead_choices = self.client.get(URL, {"tab": "funding", "view": "table"}).context["staff_users"]
        self.assertEqual(set(lead_choices), {self.staff, self.val, self.other})
        person_choices = self.client.get(URL, {"tab": self.job_search.slug, "view": "table"}).context["staff_users"]
        self.assertEqual(set(person_choices), {self.staff})


class ActionsTest(VolunteerLeadsTestCase):
    def test_works_lead_enrollments_like_staff(self):
        response = self.post("move", self.lead_enrollment, {"step": self.awarded.pk})
        self.assertEqual(events(response)["toast"]["text"], "Moved to Awarded.")
        response = self.post("assign", self.lead_enrollment, {"assignee": self.val.pk})
        self.assertEqual(events(response)["toast"]["text"], "Assigned to Val.")
        response = self.post("note", self.lead_enrollment, {"text": "Called them"})
        self.assertEqual(events(response)["toast"]["text"], "Note added.")
        response = self.post("status", self.lead_enrollment, {"status": "completed"})
        self.assertEqual(events(response)["toast"]["text"], "Status set to Completed.")
        response = self.post("reopen", self.lead_enrollment)
        self.assertEqual(events(response)["toast"]["text"], "Reopened Funding.")
        self.lead_enrollment.refresh_from_db()
        self.assertEqual((self.lead_enrollment.current_step, self.lead_enrollment.assignee), (self.awarded, self.val))
        self.assertEqual(self.acme.activities.filter(actor=self.val).count(), 5)

    def test_assign_to_another_volunteer(self):
        self.post("assign", self.lead_enrollment, {"assignee": self.val.pk})
        self.post("assign", self.lead_enrollment, {"assignee": self.other.pk})
        self.lead_enrollment.refresh_from_db()
        self.assertEqual(self.lead_enrollment.assignee, self.other)

    def test_person_enrollments_are_refused(self):
        step = Step.objects.filter(phase__flow=self.job_search).last()
        for name, data in [
            ("move", {"step": step.pk}),
            ("assign", {"assignee": self.val.pk}),
            ("status", {"status": "paused"}),
            ("reopen", {}),
            ("note", {"text": "hi"}),
            ("session", {}),
            ("enroll", {}),
            ("triage", {}),
        ]:
            with self.subTest(name=name):
                self.assertEqual(self.post(name, self.person_enrollment, data).status_code, 403)
        self.assertEqual(self.client.get(reverse("pipeline:panel", args=[self.vet.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("pipeline:person_note", args=[self.vet.pk]), {"text": "x"}).status_code, 403)

    def test_missing_enrollment_is_refused_not_404(self):
        self.assertEqual(self.client.post(reverse("pipeline:note", args=[999999]), {"text": "hi"}).status_code, 403)

    def test_lead_page_links_to_the_board_and_badges_the_volunteer(self):
        self.post("note", self.lead_enrollment, {"text": "Called them"})
        response = self.client.get(self.acme.get_absolute_url())
        self.assertContains(response, f"{URL}?tab=funding")
        self.assertContains(response, ">Volunteer</span>")


class AssignTest(VolunteerLeadsTestCase):
    def test_volunteers_can_be_assigned_to_leads_only(self):
        services.assign(self.lead_enrollment, self.val, self.staff)
        with self.assertRaisesMessage(ValidationError, "Only active staff can be assigned."):
            services.assign(self.person_enrollment, self.val, self.staff)
        with self.assertRaisesMessage(ValidationError, "Only active staff can be assigned."):
            services.enroll(self.vet, Flow.objects.get(slug="boot-camp"), self.staff, assignee=self.val)

    def test_not_without_the_permission_or_when_inactive(self):
        for user in (volunteer("nobody@example.com", groups=()), volunteer("gone@example.com", is_active=False)):
            with self.subTest(user=user.email), self.assertRaisesMessage(ValidationError, "volunteers who work leads"):
                services.assign(self.lead_enrollment, user, self.staff)
        self.assertEqual(Enrollment.objects.get(pk=self.lead_enrollment.pk).assignee, self.other)
