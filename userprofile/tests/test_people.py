import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from cold_apply.models import Participant
from pipeline import services
from pipeline.models import Activity, Flow
from resume.models import Concentration, Degree, Education, Organization
from userprofile import people
from userprofile.models import Profile

from .test_onboarding import verified_user
from .test_service_doc import reviewer

MEDIA_ROOT = tempfile.mkdtemp()


def full_person(email="vet@example.com"):
    user = User.objects.create_user(email, email, first_name="Pat", last_name="Vet")
    Profile.objects.create(
        user=user, phone="555-0100", city="Austin", state="TX", is_veteran=True, service_branch="ARMY",
        rank_at_separation="E-5", special_skills="Welding", job_links="https://example.com/job", dnc=True,
    )
    return user


class PeopleTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = verified_user("staff@example.com", is_staff=True)
        cls.job_search = Flow.objects.get(slug="resume-job-search")
        cls.intake = Flow.objects.get(slug="intake")

    def setUp(self):
        self.client.force_login(self.staff)


class AccessTest(PeopleTestCase):
    def test_staff_only(self):
        person = full_person()
        for url in (reverse("staff_people"), reverse("staff_person", args=[person.pk])):
            with self.subTest(url=url):
                self.client.force_login(person)
                self.assertEqual(self.client.get(url).status_code, 403)
                self.client.logout()
                self.assertIn(reverse("account_login"), self.client.get(url)["Location"])

    def test_missing_person_and_staff_are_404(self):
        self.assertEqual(self.client.get(reverse("staff_person", args=[999999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("staff_person", args=[self.staff.pk])).status_code, 404)


class WorkspaceTest(PeopleTestCase):
    def test_bare_account_renders(self):
        bare = User.objects.create_user("bare@example.com", "bare@example.com")
        response = self.client.get(reverse("staff_person", args=[bare.pk]))
        for text in ("No profile yet", "Not in any flow", "Not given yet.", "Nothing yet."):
            self.assertContains(response, text)
        self.assertNotContains(response, "Work tools")
        self.assertEqual([flow.slug for flow in response.context["joinable_flows"]][0], "intake")

    def test_full_person_renders(self):
        person = full_person()
        participant = Participant.objects.create(user=person)
        Education.objects.create(
            participant=participant, org=Organization.objects.create(name="State U"),
            degree=Degree.objects.create(name="Bachelor of Science", abbr="BS"),
            concentration=Concentration.objects.create(name="Biology"),
        )
        enrollment = services.enroll(person, self.job_search, self.staff, assignee=self.staff)
        services.add_note(person, self.staff, "Called about resume", kind=Activity.Kind.PHONE, enrollment=enrollment)
        response = self.client.get(reverse("staff_person", args=[person.pk]))
        for text in (
            "Pat Vet", "Do not contact", "555-0100", "Austin, TX", "US Army", "E-5", "Welding",
            'href="https://example.com/job"', "Called about resume", "Resume &amp; Job Search",
            "State U", "Biology", "Jobs and tailored resumes",
        ):
            self.assertContains(response, text)
        self.assertContains(response, reverse("cold_apply:participant_detail", args=[participant.pk]))
        self.assertContains(response, f'id="enrollment-{enrollment.pk}"')
        # Already in Resume & Job Search, so it isn't offered again
        self.assertNotIn(self.job_search, response.context["joinable_flows"])

    def test_non_veteran(self):
        person = User.objects.create_user("civ@example.com", "civ@example.com")
        Profile.objects.create(user=person, is_veteran=False)
        self.assertContains(self.client.get(reverse("staff_person", args=[person.pk])), "Not a veteran.")

    def test_people_in_intake_join_flows_through_triage(self):
        person = full_person()
        services.enroll(person, self.intake, None)
        response = self.client.get(reverse("staff_person", args=[person.pk]))
        self.assertEqual(response.context["joinable_flows"], [])
        self.assertNotContains(response, reverse("pipeline:person_enroll", args=[person.pk]))

    def test_parts_for_refresh(self):
        person = full_person()
        services.enroll(person, self.job_search, None)
        url = reverse("staff_person", args=[person.pk])
        self.assertTemplateUsed(self.client.get(url, {"part": "flows"}), "userprofile/people/person_flows.html")
        self.assertTemplateUsed(self.client.get(url, {"part": "timeline"}), "pipeline/partials/timeline.html")

    @override_settings(GS_BUCKET_NAME="test-bucket")
    def test_resume_link_is_signed(self):
        person = full_person()
        Profile.objects.filter(user=person).update(resume="uploads/resume.pdf")
        with mock.patch("userprofile.people.generate_signed_url", return_value="https://signed.example/r") as signed:
            response = self.client.get(reverse("staff_person", args=[person.pk]))
        self.assertContains(response, 'href="https://signed.example/r"')
        self.assertEqual(signed.call_args.kwargs["object_name"], "uploads/resume.pdf")


@override_settings(MEDIA_ROOT=MEDIA_ROOT, GS_BUCKET_NAME="test-bucket")
class DD214Test(PeopleTestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.person = full_person()
        Profile.objects.get(user=self.person).service_doc.save("dd214.pdf", ContentFile(b"%PDF-1.4"))
        self.url = reverse("staff_person", args=[self.person.pk])
        self.doc_url = reverse("service_doc", args=[self.person.pk])

    def test_link_hidden_without_permission(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, self.doc_url)
        self.assertContains(response, "Only veteran reviewers can open the DD214.")

    def test_link_shown_to_reviewers_and_superusers(self):
        for user in (reviewer(), verified_user("super@example.com", is_staff=True, is_superuser=True)):
            with self.subTest(user=user.email):
                self.client.force_login(user)
                self.assertContains(self.client.get(self.url), self.doc_url)

    def test_opening_is_on_the_timeline(self):
        opener = reviewer()
        self.client.force_login(opener)
        with mock.patch("userprofile.views.generate_signed_url", return_value="https://signed.example/d"):
            self.assertEqual(self.client.get(self.doc_url).status_code, 302)
        entry = Activity.objects.get(person=self.person, kind="document_opened")
        self.assertEqual((entry.text, entry.actor), ("DD214", opener))
        self.assertContains(self.client.get(self.url), "Document opened")


class PeopleSearchTest(PeopleTestCase):
    def test_lists_people_not_staff_or_bare_accounts(self):
        pat = full_person()
        in_flow = User.objects.create_user("flow@example.com", "flow@example.com")
        services.enroll(in_flow, self.job_search, None)
        User.objects.create_user("bare@example.com", "bare@example.com")
        response = self.client.get(reverse("staff_people"))
        self.assertEqual({p.email for p in response.context["page"].object_list}, {pat.email, in_flow.email})
        self.assertContains(response, reverse("staff_person", args=[pat.pk]))
        self.assertContains(response, "Do not contact")

    def test_search_and_htmx(self):
        full_person()
        full_person("other@example.com")
        response = self.client.get(reverse("staff_people"), {"q": "other"}, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "userprofile/people/people_table.html")
        self.assertEqual([p.email for p in response.context["page"].object_list], ["other@example.com"])
        self.assertContains(self.client.get(reverse("staff_people"), {"q": "nobody"}), "Nobody matches")

    def test_pages(self):
        for i in range(3):
            full_person(f"p{i}@example.com")
        with mock.patch.object(people, "PAGE_SIZE", 2):
            response = self.client.get(reverse("staff_people"), {"page": 2})
        self.assertEqual(len(response.context["page"].object_list), 1)
        self.assertContains(response, "Page 2 of 2")


class ParticipantPageTest(PeopleTestCase):
    """The participant page is the jobs tool now; staff details moved to the workspace"""

    def test_staff_get_workspace_link_and_no_staff_blocks(self):
        person = full_person()
        participant = Participant.objects.create(user=person)
        url = reverse("cold_apply:participant_detail", args=[participant.pk])
        response = self.client.get(url)
        self.assertContains(response, reverse("staff_person", args=[person.pk]))
        for gone in ("Do Not Contact", "Contactable", "Highest Education", "Update Participant Phase"):
            self.assertNotContains(response, gone)
        self.client.force_login(person)
        self.assertNotContains(self.client.get(url), "Open staff workspace")

    def test_dashboard_names_link_to_workspace(self):
        person = full_person()
        services.enroll(person, self.job_search, None)
        response = self.client.get(reverse("staff"), {"tab": "resume-job-search"})
        self.assertContains(response, f'href="{reverse("staff_person", args=[person.pk])}"')
