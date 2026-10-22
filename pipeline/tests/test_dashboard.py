from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from pipeline import services
from pipeline.models import Enrollment, Flow, Step
from userprofile.models import Profile

URL = reverse("staff")


def person(email, first="", last="", **profile):
    user = User.objects.create_user(email, email, first_name=first, last_name=last)
    Profile.objects.create(user=user, **profile)
    return user


def names(response):
    return sorted(e.person.email for e in response.context["rows"])


class DashboardTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("staff@example.com", is_staff=True, first_name="Sam", last_name="Staff")
        cls.other_staff = User.objects.create_user("alex@example.com", is_staff=True)
        cls.intake = Flow.objects.get(slug="intake")
        cls.job_search = Flow.objects.get(slug="resume-job-search")
        cls.verify, cls.triage = Step.objects.filter(phase__flow=cls.intake)

        cls.applicant = services.enroll(person("pat@example.com", "Pat", "Applicant"), cls.intake, None)
        cls.triaged = services.enroll(person("tri@example.com", "Tri", "Age"), cls.intake, None, step=cls.triage)
        cls.mine = services.enroll(
            person("mine@example.com", "Mia", "Mine", dnc=True), cls.job_search, None, assignee=cls.staff
        )
        cls.theirs = services.enroll(person("theirs@example.com"), cls.job_search, None, assignee=cls.other_staff)
        cls.loose = services.enroll(person("loose@example.com", "Lou", "Loose"), cls.job_search, None)
        services.set_status(cls.loose, Enrollment.Status.PAUSED, None)
        final = Step.objects.get(phase__flow=cls.job_search, completes_flow=True)
        done = services.enroll(person("done@example.com"), cls.job_search, None, step=final)
        services.set_status(done, Enrollment.Status.COMPLETED, None)
        Enrollment.objects.filter(pk=cls.theirs.pk).update(step_entered_at=timezone.now() - timedelta(days=30))

    def setUp(self):
        self.client.force_login(self.staff)


class AccessTest(DashboardTestCase):
    def test_staff_only(self):
        for url in (URL, reverse("staff_flows")):
            with self.subTest(url=url):
                self.client.logout()
                self.assertIn(reverse("account_login"), self.client.get(url)["Location"])
                self.client.force_login(self.applicant.person)
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_unknown_tab_is_404(self):
        self.assertEqual(self.client.get(URL, {"tab": "nope"}).status_code, 404)


class TabsTest(DashboardTestCase):
    def test_intake_is_the_default_tab(self):
        response = self.client.get(URL)
        self.assertEqual(response.context["tab"], "intake")
        self.assertEqual(names(response), ["pat@example.com", "tri@example.com"])
        self.assertContains(response, "Verify Veteran Status")

    def test_flow_tab_shows_open_enrollments_only(self):
        response = self.client.get(URL, {"tab": "resume-job-search"})
        self.assertEqual(names(response), ["loose@example.com", "mine@example.com", "theirs@example.com"])
        self.assertContains(response, "Do not contact")
        self.assertContains(response, "Paused")

    def test_my_people_and_everyone(self):
        self.assertEqual(names(self.client.get(URL, {"tab": "mine"})), ["mine@example.com"])
        self.assertEqual(len(self.client.get(URL, {"tab": "all"}).context["rows"]), 5)

    def test_tabs_list_active_flows_with_intake_first(self):
        Flow.objects.filter(slug="nurture").update(active=False)
        labels = [label for _, label in self.client.get(URL).context["tabs"]]
        self.assertEqual(labels, ["Intake", "Resume & Job Search", "Boot Camp", "My people", "Everyone"])


class FiltersTest(DashboardTestCase):
    def rows(self, **params):
        return names(self.client.get(URL, {"tab": "resume-job-search", **params}))

    def test_assignee(self):
        self.assertEqual(self.rows(assignee="me"), ["mine@example.com"])
        self.assertEqual(self.rows(assignee="unassigned"), ["loose@example.com"])

    def test_status(self):
        self.assertEqual(self.rows(status="paused"), ["loose@example.com"])
        self.assertEqual(self.rows(status="completed"), ["done@example.com"])

    def test_days_in_step(self):
        self.assertEqual(self.rows(days=14), ["theirs@example.com"])

    def test_phase_and_step(self):
        step = self.job_search.first_step()
        self.assertEqual(len(self.rows(phase=step.phase_id)), 3)
        response = self.client.get(URL, {"tab": "intake", "step": self.triage.pk})
        self.assertEqual(names(response), ["tri@example.com"])

    def test_search_matches_every_word(self):
        self.assertEqual(self.rows(q="mia mine"), ["mine@example.com"])
        self.assertEqual(self.rows(q="LOOSE@"), ["loose@example.com"])
        self.assertEqual(self.rows(q="mia loose"), [])

    def test_invalid_filter_shows_error(self):
        response = self.client.get(URL, {"days": "0"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Some filters aren't valid")

    def test_htmx_gets_only_the_table(self):
        response = self.client.get(URL, {"tab": "resume-job-search", "q": "mia"}, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "pipeline/partials/enrollment_table.html")
        self.assertTemplateNotUsed(response, "pipeline/dashboard.html")
        self.assertContains(response, f'id="enrollment-{self.mine.pk}"')


class HeaderCountsTest(DashboardTestCase):
    def test_counts_and_links(self):
        counts = {item["label"]: item for item in self.client.get(URL).context["counts"]}
        self.assertEqual(
            [(label, item["count"]) for label, item in counts.items()],
            [("In Verify Veteran Status", 1), ("In Triage", 1), ("Unassigned", 3), ("In step over 14 days", 1)],
        )
        self.assertEqual(counts["In Triage"]["params"], {"tab": "intake", "step": self.triage.pk})


class ReviewLinkTest(DashboardTestCase):
    def test_only_reviewers_see_review_link(self):
        review_url = reverse("userprofile:veteran_status_update_view", args=[self.applicant.person_id])
        self.assertNotContains(self.client.get(URL), review_url)
        self.staff.groups.add(Group.objects.get(name="Veteran reviewers"))
        self.assertContains(self.client.get(URL), review_url)


class QueryCountTest(TestCase):
    def test_queries_do_not_grow_with_rows(self):
        staff = User.objects.create_user("staff@example.com", is_staff=True)
        flow = Flow.objects.get(slug="resume-job-search")
        self.client.force_login(staff)

        def queries_for(count):
            for i in range(Enrollment.objects.count(), count):
                user = person(f"p{i}@example.com", "P", str(i))
                enrollment = services.enroll(user, flow, staff, assignee=staff)
                services.add_note(user, staff, "hello", enrollment=enrollment)
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(URL, {"tab": "all"})
            self.assertEqual(len(response.context["rows"]), count)
            return len(queries)

        self.assertEqual(queries_for(5), queries_for(50))


class FlowsPageTest(DashboardTestCase):
    def test_lists_steps_with_counts(self):
        response = self.client.get(reverse("staff_flows"))
        self.assertContains(response, "Verify Veteran Status")
        self.assertContains(response, "Reviewers only")
        steps = {
            step.title: step.open
            for flow in response.context["flows"]
            for phase in flow.phases.all()
            for step in phase.steps.all()
        }
        self.assertEqual((steps["Verify Veteran Status"], steps["Triage"]), (1, 1))
        self.assertEqual(list(steps)[:2], ["Verify Veteran Status", "Triage"])
