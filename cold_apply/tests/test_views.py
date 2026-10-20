import datetime
import importlib
import os
from urllib.parse import urlencode

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright

from cold_apply.forms import ResumeConfigForm
from cold_apply.models import Phase, Skill, SkillBullet, Step
from cold_apply.tests.factories import (
    ExperienceFactory,
    JobFactory,
    OrganizationFactory,
    ParticipantFactory,
    PositionFactory,
    UserFactory,
)
from pipeline import services
from pipeline.models import Flow
from resume.models import (
    Bullet,
    CertProjectActivity,
    Concentration,
    Degree,
    Education,
    Experience,
    Organization,
)
from resume.pdf import (
    RESUME_TEMPLATE_SECTIONS_JSON,
    ResumeCoreTemplates,
    ResumeFormatChoices,
    ResumeSections,
)

seed_flows = importlib.import_module("pipeline.migrations.0002_seed_flows")


def make_resume_participant():
    """A participant with one job and three experiences with distinct start dates,
    each experience carrying factory bullets."""
    phase = Phase.objects.create(title="Phase 1", start="start", end="end", result="result", active=True)
    step = Step.objects.create(title="Phase 1.0", description="First step", phase=phase)
    user = UserFactory(first_name="Jane", last_name="Veteran", email="jane@example.com")
    participant = ParticipantFactory(user=user, current_step=step, jobs=[], experiences=[])
    # The staff dashboard lists people by enrollment
    services.enroll(user, Flow.objects.get(slug="resume-job-search"), actor=None)
    JobFactory(participant=participant, title=PositionFactory(title="Software Engineer"), status="Open")
    for year in (2018, 2020, 2022):
        ExperienceFactory(
            participant=participant,
            org=OrganizationFactory(),
            position=PositionFactory(),
            start_date=datetime.date(year, 1, 1),
            end_date=datetime.date(year + 1, 1, 1),
        )
    return participant


def login_redirect_url(url):
    return resolve_url(settings.LOGIN_URL) + f"?next={url}"


class ColdApplyBrowserTest(StaticLiveServerTestCase):
    """Playwright end to end tests for the cold_apply app."""

    @classmethod
    def setUpClass(cls):
        # playwright sync api uses an internal event loop,
        # any calls to certain parts of django where an
        # event loop is running will error
        # https://docs.djangoproject.com/en/4.2/topics/async/#async-safety
        # we're only testing so we can allow the unsafe async calls

        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        # TransactionTestCases flush the database, including the flows seeded by migrations
        if not Flow.objects.exists():
            seed_flows.seed_flows(apps)
        User.objects.create_superuser(username="admin@example.com", email="admin@example.com", password="admin")
        self.participant = make_resume_participant()

    def test_click_through_to_config_page(self):
        """
        - Login and navigate to the config page for a job.
        - Checks that config page is in a popup.
        """
        context = self.browser.new_context()
        page = context.new_page()
        dashboard = f"{reverse('staff')}?tab=resume-job-search"
        page.goto(f"{self.live_server_url}{reverse('account_login')}?{urlencode({'next': dashboard})}")
        page.locator("#id_login").fill("admin@example.com")
        page.locator("#id_password").fill("admin")
        page.get_by_role("button", name="Sign In").click()

        # The name opens the quick view; the participant page is one click further
        page.get_by_role("link", name="Jane Veteran").first.click()
        page.get_by_role("link", name="Open full page").click()
        page.get_by_role("link", name="Software Engineer").first.click()
        with page.expect_popup() as page1_info:
            page.get_by_role("link", name="Tailor Resume").click()
        page1 = page1_info.value
        for experience in Experience.objects.filter(participant=self.participant):
            page1.get_by_label(str(experience)).check()

        page1.get_by_role("button", name="Preview Content").click()
        assert page1.get_by_text("Jane Veteran").first.is_visible()
        page1.get_by_role("button", name="Back to Configuration").click()

        context.close()


class EducationUpdateViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser(username="admin@example.com", email="admin@example.com", password="admin")
        cls.education = Education.objects.create(
            participant=ParticipantFactory(jobs=[], experiences=[]),
            org=OrganizationFactory(),
            degree=Degree.objects.create(name="Bachelor of Science", abbr="BS"),
            concentration=Concentration.objects.create(name="Computer Science"),
        )

    def test_view_200(self):
        self.client.force_login(self.staff)

        url = reverse("cold_apply:update_education", args=[self.education.id])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        unauth_response = self.client.get(url)
        self.assertRedirects(unauth_response, login_redirect_url(url))


class ParticipantUpdateViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser(username="admin@example.com", email="admin@example.com", password="admin")
        cls.participant = ParticipantFactory(jobs=[], experiences=[])

    def test_view_200(self):
        self.client.force_login(self.staff)

        url = reverse("cold_apply:update_participant", args=[self.participant.id])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        unauth_response = self.client.get(url)
        self.assertRedirects(unauth_response, login_redirect_url(url))


class ConfigureTailoredResumeViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="testuser", password="testpassword")
        cls.participant = make_resume_participant()
        cls.job = cls.participant.job_set.first()
        cls.config_url = reverse("cold_apply:configure_tailored_resume", args=[cls.job.pk])

    def test_get_request(self):
        self.client.force_login(self.user)
        response = self.client.get(self.config_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "cold_apply/configure_tailored_resume.html")
        self.assertIsInstance(response.context["form"], ResumeConfigForm)
        self.assertEqual(response.context["job"], self.job)
        self.assertEqual(
            response.context["resume_template_sections_json"],
            RESUME_TEMPLATE_SECTIONS_JSON,
        )

    def test_job_not_found(self):
        self.client.force_login(self.user)
        url = reverse("cold_apply:configure_tailored_resume", args=[12345])  # Non-existent job ID
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_view_is_login_required(self):
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, login_redirect_url(self.config_url))


class TailoredResumeViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="testuser", password="testpassword")
        cls.participant = make_resume_participant()
        cls.job = cls.participant.job_set.first()
        cls.url = reverse("cold_apply:tailored_resume", args=[cls.job.id])

        bullets = Bullet.objects.filter(experience__participant=cls.participant)
        for i, bullet in enumerate(bullets[:3], start=1):
            SkillBullet.objects.create(bullet=bullet, skill=Skill.objects.create(title=f"test skill {i}"))

        cls.cert1 = CertProjectActivity.objects.create(
            org=Organization.objects.first(),
            title="test cert 1",
            description="test cert 1 description",
            variety="Certification",
            participant=cls.participant,
        )
        cls.cert2 = CertProjectActivity.objects.create(
            org=Organization.objects.first(),
            title="test cert 1",
            description="test cert 1 description",
            variety="Award",
            participant=cls.participant,
        )

    def resume_params(self, **overrides):
        return {
            "sections": [v for v, k in ResumeSections.choices],
            "bullets_content": ResumeFormatChoices.CHRONOLOGICAL,
            "resume_template": ResumeCoreTemplates.STANDARD,
            "experiences": Experience.objects.filter(participant=self.participant).values_list("id", flat=True),
            **overrides,
        }

    def test_response_is_pdf(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url, self.resume_params())

        self.assertTemplateUsed(response, f"resume/resume_{ResumeCoreTemplates.STANDARD}.html")
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response.status_code, 200)

    def test_preview_response_is_html(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url, self.resume_params(preview=True))

        self.assertTemplateUsed(response, f"resume/resume_{ResumeCoreTemplates.STANDARD}.html")
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(response.status_code, 200)

    def test_post_request_invalid_form(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url + f"?{urlencode({'wrong': True})}")
        self.assertRedirects(
            response,
            reverse("cold_apply:configure_tailored_resume", args=[self.job.pk]),
        )

    def test_extra_skills_are_filtered(self):
        self.client.force_login(self.user)
        extra_skills = list(
            Skill.objects.filter(bullet__experience__participant=self.participant)
            .distinct()
            .values_list("id", flat=True)
        )[:2]

        data = self.resume_params(
            bullets_content=ResumeFormatChoices.SKILLS, preview=True, extra_skills=extra_skills
        )
        response = self.client.get(self.url, data)
        self.assertQuerysetEqual(
            response.context["skills"].order_by("id"),
            Skill.objects.filter(id__in=extra_skills).order_by("id"),
        )

        data["bullets_content"] = ResumeFormatChoices.CHRONOLOGICAL
        response = self.client.get(self.url, data)
        self.assertQuerysetEqual(
            response.context["skills"].order_by("id"),
            Skill.objects.filter(id__in=extra_skills).order_by("id"),
        )

    def test_certs_are_filtered(self):
        self.client.force_login(self.user)
        certs = [self.cert1.id]

        data = self.resume_params(bullets_content=ResumeFormatChoices.SKILLS, preview=True, certifications=certs)
        response = self.client.get(self.url, data)
        self.assertQuerysetEqual(
            response.context["certifications"].order_by("id"),
            CertProjectActivity.objects.filter(id__in=certs).order_by("id"),
        )

    def test_experiences_are_chronological(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url, self.resume_params(preview=True))

        experiences = list(response.context["chronological_experiences"])
        self.assertEqual(len(experiences), 3)
        for i, ex in enumerate(experiences[:-1]):
            self.assertGreater(ex["obj"].start_date, experiences[i + 1]["obj"].start_date)
