import json

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from pipeline import services
from pipeline.models import Activity, Enrollment, Flow, Step
from userprofile.models import Profile

from .test_dashboard import person


def events(response):
    return json.loads(response.get("HX-Trigger", "{}"))


class ActionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("staff@example.com", is_staff=True, first_name="Sam", last_name="Staff")
        cls.alex = User.objects.create_user("alex@example.com", is_staff=True, first_name="Alex", last_name="Lee")
        cls.intake = Flow.objects.get(slug="intake")
        cls.job_search = Flow.objects.get(slug="resume-job-search")
        cls.boot_camp = Flow.objects.get(slug="boot-camp")
        cls.verify, cls.triage = Step.objects.filter(phase__flow=cls.intake)
        cls.vet = person("vet@example.com", "Pat", "Vet")

    def setUp(self):
        self.client.force_login(self.staff)
        self.enrollment = services.enroll(self.vet, self.job_search, None)

    def post(self, name, data=None, enrollment=None):
        return self.client.post(reverse(f"pipeline:{name}", args=[(enrollment or self.enrollment).pk]), data or {})

    def assertChanged(self, response, text):
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pipeline/partials/enrollment_row.html")
        self.assertTrue(events(response)["enrollment-changed"])
        self.assertEqual(events(response)["toast"], {"category": "success", "text": text})

    def assertRefused(self, response, text):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Reswap"], "none")
        self.assertNotIn("enrollment-changed", events(response))
        self.assertEqual(events(response)["toast"]["category"], "error")
        self.assertIn(text, events(response)["toast"]["text"])

    def refresh(self):
        self.enrollment.refresh_from_db()
        return self.enrollment


class AccessTest(ActionTestCase):
    def test_staff_only_and_post_only(self):
        url = reverse("pipeline:note", args=[self.enrollment.pk])
        self.client.force_login(self.vet)
        self.assertEqual(self.client.post(url, {"text": "hi"}).status_code, 403)
        self.client.logout()
        self.assertIn(reverse("account_login"), self.client.post(url, {"text": "hi"})["Location"])
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertFalse(Activity.objects.filter(kind="note").exists())

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        response = client.post(reverse("pipeline:note", args=[self.enrollment.pk]), {"text": "hi"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Activity.objects.filter(kind="note").exists())

    def test_missing_enrollment_is_404(self):
        for name in ("move", "assign", "status", "note", "enroll", "triage"):
            with self.subTest(action=name):
                self.assertEqual(self.client.post(reverse(f"pipeline:{name}", args=[999999])).status_code, 404)


class MoveTest(ActionTestCase):
    def test_move(self):
        step = Step.objects.filter(phase__flow=self.job_search).last()
        response = self.post("move", {"step": step.pk})
        self.assertChanged(response, f"Moved to {step.title}.")
        self.assertEqual(self.refresh().current_step, step)
        self.assertContains(response, f'<option value="{step.pk}" selected>')

    def test_step_from_another_flow_refused(self):
        self.assertRefused(self.post("move", {"step": self.triage.pk}), "isn't part of")

    def test_missing_or_bad_step_refused(self):
        for value in ("", "abc", "999999"):
            with self.subTest(step=value):
                self.assertRefused(self.post("move", {"step": value}), "Choose a step")

    def test_gated_step_refused_without_permission_and_select_disabled(self):
        intake = services.enroll(self.vet, self.intake, None)
        self.assertRefused(self.post("move", {"step": self.triage.pk}, intake), "Verify Veteran Status")
        intake.refresh_from_db()
        self.assertEqual(intake.current_step, self.verify)
        page = self.client.get(reverse("staff"))
        self.assertContains(page, "Only veteran reviewers can move people off Verify Veteran Status")

    def test_reviewer_can_leave_gated_step(self):
        self.staff.groups.add(Group.objects.get(name="Veteran reviewers"))
        intake = services.enroll(self.vet, self.intake, None)
        self.assertChanged(self.post("move", {"step": self.triage.pk}, intake), "Moved to Triage.")


class AssignTest(ActionTestCase):
    def test_assign_and_unassign(self):
        self.assertChanged(self.post("assign", {"assignee": self.alex.pk}), "Assigned to Alex Lee.")
        self.assertEqual(self.refresh().assignee, self.alex)
        self.assertChanged(self.post("assign", {"assignee": ""}), "Unassigned.")
        self.assertIsNone(self.refresh().assignee)

    def test_non_staff_refused(self):
        self.assertRefused(self.post("assign", {"assignee": self.vet.pk}), "Only active staff")
        self.assertRefused(self.post("assign", {"assignee": "abc"}), "Choose someone")


class StatusTest(ActionTestCase):
    def test_pause_and_reactivate(self):
        self.assertChanged(self.post("status", {"status": "paused"}), "Status set to Paused.")
        self.assertChanged(self.post("status", {"status": "active"}), "Status set to Active.")

    def test_rejection_needs_reason(self):
        self.assertRefused(self.post("status", {"status": "rejected", "reason": " "}), "reason")
        self.assertChanged(self.post("status", {"status": "rejected", "reason": "Unclear DD214"}), "Status set to Rejected.")
        self.assertEqual(Activity.objects.get(kind="status_change").text, "Unclear DD214")

    def test_unknown_status_refused(self):
        self.assertRefused(self.post("status", {"status": "lost"}), "Unknown status")

    def test_only_allowed_endings_offered(self):
        response = self.client.get(reverse("staff"), {"tab": "resume-job-search"})
        self.assertContains(response, 'name="status" value="withdrawn"')
        self.assertNotContains(response, 'name="status" value="completed"')
        self.assertNotContains(response, 'name="status" value="dropped"')
        self.assertRefused(self.post("status", {"status": "completed"}), "Move them to Service Complete first.")

    def test_ended_enrollment_can_be_reopened(self):
        response = self.post("status", {"status": "withdrawn"})
        self.assertChanged(response, "Status set to Withdrawn.")
        self.assertContains(response, reverse("pipeline:reopen", args=[self.enrollment.pk]))
        self.assertRefused(self.post("status", {"status": "active"}), "Reopen it first")
        self.assertChanged(self.post("reopen"), "Reopened Resume & Job Search.")
        self.assertEqual((self.refresh().status, self.enrollment.ended_at), ("active", None))

    def test_reopen_refused_when_enrolled_again(self):
        self.post("status", {"status": "withdrawn"})
        services.enroll(self.vet, self.job_search, None)
        self.assertRefused(self.post("reopen"), "already has an open")


class NoteTest(ActionTestCase):
    def test_note_on_enrollment(self):
        self.assertChanged(self.post("note", {"kind": "phone", "text": "Left voicemail"}), "Note added.")
        note = Activity.objects.get(kind="phone")
        self.assertEqual((note.text, note.enrollment, note.actor), ("Left voicemail", self.enrollment, self.staff))

    def test_empty_or_system_kind_refused(self):
        self.assertRefused(self.post("note", {"text": " "}), "needs some text")
        self.assertRefused(self.post("note", {"kind": "step_change", "text": "x"}), "recorded automatically")


class EnrollAndTriageTest(ActionTestCase):
    def test_enroll_in_more_flows(self):
        response = self.post("enroll", {"flows": [self.boot_camp.pk, self.job_search.pk]})
        self.assertChanged(response, "Enrolled in Boot Camp.")
        self.assertEqual(Enrollment.objects.filter(person=self.vet, ended_at__isnull=True).count(), 2)

    def test_enroll_needs_a_flow(self):
        self.assertRefused(self.post("enroll", {}), "Choose at least one flow")
        self.assertRefused(self.post("enroll", {"flows": ["abc"]}), "Choose at least one flow")

    def test_triage_enrolls_and_completes_intake(self):
        intake = services.enroll(person("new@example.com"), self.intake, None, step=self.triage)
        response = self.post("triage", {"flows": [self.boot_camp.pk, self.job_search.pk]}, intake)
        self.assertChanged(response, "Triaged into Resume & Job Search, Boot Camp.")
        intake.refresh_from_db()
        self.assertEqual(intake.status, Enrollment.Status.COMPLETED)
        self.assertEqual(
            set(Enrollment.objects.filter(person=intake.person, ended_at__isnull=True).values_list("flow__slug", flat=True)),
            {"resume-job-search", "boot-camp"},
        )

    def test_triage_only_for_intake_and_needs_a_flow(self):
        self.assertRefused(self.post("triage", {"flows": [self.boot_camp.pk]}), "Only Intake")
        intake = services.enroll(person("new@example.com"), self.intake, None, step=self.triage)
        self.assertRefused(self.post("triage", {}, intake), "Choose at least one flow")

    def test_triage_from_gated_step_refused_without_permission(self):
        intake = services.enroll(person("new@example.com"), self.intake, None)
        self.assertRefused(self.post("triage", {"flows": [self.boot_camp.pk]}, intake), "Verify Veteran Status")
        self.assertFalse(Enrollment.objects.filter(flow=self.boot_camp).exists())

    def test_intake_rows_offer_triage_after_review_only(self):
        services.enroll(person("new@example.com"), self.intake, None, step=self.triage)
        services.enroll(person("waiting@example.com"), self.intake, None)
        page = self.client.get(reverse("staff"))
        self.assertContains(page, "Complete triage", count=1)
        self.assertContains(page, "Triage opens once veteran status is reviewed.", count=1)
        self.assertNotContains(page, ">Enroll</button>")


class PanelTest(ActionTestCase):
    def test_panel_shows_profile_flows_and_timeline(self):
        Profile.objects.filter(user=self.vet).update(dnc=True, phone="555-0100")
        services.add_note(self.vet, self.staff, "Prefers email")
        response = self.client.get(reverse("pipeline:panel", args=[self.vet.pk]))
        for text in ("Pat Vet", "Do not contact", "555-0100", "Resume &amp; Job Search", "Prefers email", "Sam Staff"):
            self.assertContains(response, text)

    def test_person_note(self):
        url = reverse("pipeline:person_note", args=[self.vet.pk])
        response = self.client.post(url, {"kind": "email", "text": "Sent welcome"})
        self.assertTemplateUsed(response, "pipeline/partials/timeline.html")
        self.assertContains(response, "Sent welcome")
        self.assertTrue(events(response)["enrollment-changed"])
        self.assertIsNone(Activity.objects.get(kind="email").enrollment)
        self.assertEqual(self.client.post(url, {"text": ""})["HX-Reswap"], "none")
        self.client.force_login(self.vet)
        self.assertEqual(self.client.post(url, {"text": "hi"}).status_code, 403)

    def test_person_without_profile(self):
        bare = User.objects.create_user("bare@example.com")
        self.assertContains(self.client.get(reverse("pipeline:panel", args=[bare.pk])), "Not in any flow")

    def test_staff_only_and_404(self):
        self.assertEqual(self.client.get(reverse("pipeline:panel", args=[999999])).status_code, 404)
        self.client.force_login(self.vet)
        self.assertEqual(self.client.get(reverse("pipeline:panel", args=[self.vet.pk])).status_code, 403)


class PersonEnrollTest(ActionTestCase):
    def test_enroll_from_workspace(self):
        url = reverse("pipeline:person_enroll", args=[self.vet.pk])
        response = self.client.post(url, {"flows": [self.intake.pk, self.job_search.pk]})
        self.assertEqual(response["HX-Reswap"], "none")
        self.assertEqual(events(response)["toast"]["text"], "Enrolled in Intake.")
        self.assertTrue(events(response)["enrollment-changed"])
        self.assertRefused(self.client.post(url, {}), "Choose at least one flow")
        self.client.force_login(self.vet)
        self.assertEqual(self.client.post(url, {"flows": [self.boot_camp.pk]}).status_code, 403)
