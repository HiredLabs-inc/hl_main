import django
import os
from urllib.parse import urlencode
from django.test import TestCase
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.contrib.auth.models import User

from cold_apply.forms import ResumeConfigForm
from cold_apply.models import Job, Location, Participant, SkillBullet, State
from hl_main import settings
from playwright.sync_api import Playwright, sync_playwright, expect
from cold_apply.models import Skill
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


class ColdApplyBrowserTest(StaticLiveServerTestCase):
    """Playwright end to end tests for the cold_apply app."""

    fixtures = ["cold_apply/fixtures/dev_data.json"]

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

    def test_click_through_to_config_page(self):
        """
        - Login and navigate to the config page for a job.
        - Checks that config page is in a popup.
        """
        context = self.browser.new_context()
        page = context.new_page()
        page.goto(f"{self.live_server_url}/userprofile/login/?next=/staff/")
        page.locator("#id_username").click()
        page.locator("#id_username").fill("admin")
        page.locator("#id_password").click()
        page.locator("#id_password").fill("admin")
        page.get_by_role("button", name="Login").click()
        page.get_by_role("link", name="cold_apply").click()

        page.get_by_role("link", name="Jeff Stock").click()
        page.get_by_role("link", name="Software Engineer - Early Professional").click()
        with page.expect_popup() as page1_info:
            page.get_by_role("link", name="Tailor Resume").click()
        page1 = page1_info.value
        page1.get_by_text(
            "Hired Labs, inc.: Technical Co-founder - 2022-06-15 - Present"
        ).click()
        page1.get_by_text(
            "Upwork Inc.: Program Manager, Data Analytics & Operations - 2019-12-31 - 2022-05-"
        ).click()
        page1.get_by_label(
            "Upwork Inc.: Associate Program Manager, Contingent Workforce - 2018-08-01 - 2019-12-31"
        ).check()
        page1.get_by_role("listitem").filter(has_text="Top Skills").click()
        page1.get_by_role("listitem").filter(
            has_text="Seriff Overview | Education | Skills | Certifications"
        ).locator("div").click()

        page1.get_by_text("No colors").click()
        page1.get_by_text("No colors").click()
        page1.get_by_role("button", name="Preview Content").click()
        assert page1.get_by_text("Jeff Stock").is_visible()
        page1.get_by_role("button", name="Back to Configuration").click()

        context.close()


class EducationUpdateViewTestCase(TestCase):
    fixtures = ["cold_apply/fixtures/dev_data.json"]

    @classmethod
    def setUpTestData(self):
        self.education = Education.objects.create(
            participant=Participant.objects.filter(name="Jeff Stock").first(),
            org=Organization.objects.first(),
            degree=Degree.objects.first(),
            concentration=Concentration.objects.first(),
        )

    def test_view_200(self):
        self.client.login(username="admin", password="admin")

        url = reverse("cold_apply:update_education", args=[self.education.id])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        unauth_response = self.client.get(url)
        self.assertRedirects(
            unauth_response, reverse(settings.LOGIN_URL) + f"?next={url}"
        )


class ParticipantUpdateViewTestCase(TestCase):
    fixtures = ["cold_apply/fixtures/dev_data.json"]

    def test_view_200(self):
        self.client.login(username="admin", password="admin")

        url = reverse(
            "cold_apply:update_participant", args=[Participant.objects.first().id]
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        unauth_response = self.client.get(url)
        self.assertRedirects(
            unauth_response, reverse(settings.LOGIN_URL) + f"?next={url}"
        )


class ConfigureTailoredResumeViewTest(TestCase):
    fixtures = ["cold_apply/fixtures/dev_data.json"]

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="testuser", password="testpassword"
        )
        self.participant = Participant.objects.filter(name="Jeff Stock").first()
        self.job = self.participant.job_set.first()
        self.config_url = reverse(
            "cold_apply:configure_tailored_resume", args=[self.job.pk]
        )
        self.resume_url = reverse("cold_apply:tailored_resume", args=[self.job.id])

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

        # Add assertions for other expected form errors

    def test_job_not_found(self):
        self.client.force_login(self.user)
        url = reverse(
            "cold_apply:configure_tailored_resume", args=[12345]
        )  # Non-existent job ID
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_view_is_login_required(self):
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse(settings.LOGIN_URL) + f"?next={self.config_url}"
        )


class TailoredResumeViewTestCase(TestCase):
    fixtures = ["cold_apply/fixtures/dev_data.json"]

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="testuser", password="testpassword"
        )
        # self.participant = Participant.objects.first()
        # self.position = Position.objects.create("position")
        self.participant = Participant.objects.filter(name="Jeff Stock").first()
        self.job = self.participant.job_set.first()
        self.url = reverse("cold_apply:tailored_resume", args=[self.job.id])
        skill1 = Skill.objects.create(title="test skill 1")

        skill2 = Skill.objects.create(title="test skill 2")
        skill3 = Skill.objects.create(title="test skill 3")

        bullets = Bullet.objects.filter(experience__participant=self.participant)

        bullet1 = bullets[0]
        bullet2 = bullets[1]
        bullet3 = bullets[2]

        SkillBullet.objects.create(
            bullet=bullet1,
            skill=skill1,
        )
        SkillBullet.objects.create(
            bullet=bullet2,
            skill=skill2,
        )
        SkillBullet.objects.create(
            bullet=bullet3,
            skill=skill3,
        )

        self.cert1 = CertProjectActivity.objects.create(
            org=Organization.objects.first(),
            title="test cert 1",
            description="test cert 1 description",
            variety="Certification",
            participant=self.participant,
        )
        self.cert2 = CertProjectActivity.objects.create(
            org=Organization.objects.first(),
            title="test cert 1",
            description="test cert 1 description",
            variety="Award",
            participant=self.participant,
        )

    def test_response_is_pdf(self):
        self.client.force_login(self.user)
        data = {
            "sections": [v for v, k in ResumeSections.choices],
            "bullets_content": ResumeFormatChoices.CHRONOLOGICAL,
            "resume_template": ResumeCoreTemplates.STANDARD,
            # "preview": True,
            "experiences": Experience.objects.filter(
                participant=self.participant
            ).values_list("id", flat=True),
            # "skills": [self.skill.pk],
            # "certifications": [self.certification.pk],
            # Add other form fields here with their respective values
        }
        response = self.client.get(self.url, data)

        self.assertTemplateUsed(
            response, f"resume/resume_{ResumeCoreTemplates.STANDARD}.html"
        )
        self.assertEqual(response["Content-Type"], "application/pdf")

        self.assertEqual(response.status_code, 200)

    def test_preview_response_is_html(self):
        self.client.force_login(self.user)
        data = {
            "sections": [v for v, k in ResumeSections.choices],
            "bullets_content": ResumeFormatChoices.CHRONOLOGICAL,
            "resume_template": ResumeCoreTemplates.STANDARD,
            "preview": True,
            "experiences": Experience.objects.filter(
                participant=self.participant
            ).values_list("id", flat=True),
            # "skills": [self.skill.pk],
            # "certifications": [self.certification.pk],
            # Add other form fields here with their respective values
        }
        response = self.client.get(self.url, data)
        self.assertTemplateUsed(
            response, f"resume/resume_{ResumeCoreTemplates.STANDARD}.html"
        )
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")

        self.assertEqual(response.status_code, 200)

    def test_post_request_invalid_form(self):
        self.client.force_login(self.user)
        data = {"wrong": True}
        response = self.client.get(self.url + f"?{urlencode(data)}")
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

        data = {
            "sections": [v for v, k in ResumeSections.choices],
            "bullets_content": ResumeFormatChoices.SKILLS,
            "resume_template": ResumeCoreTemplates.STANDARD,
            "preview": True,
            "extra_skills": extra_skills,
            "experiences": Experience.objects.filter(
                participant=self.participant
            ).values_list("id", flat=True),
        }

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

        data = {
            "sections": [v for v, k in ResumeSections.choices],
            "bullets_content": ResumeFormatChoices.SKILLS,
            "resume_template": ResumeCoreTemplates.STANDARD,
            "preview": True,
            "certifications": certs,
            "experiences": Experience.objects.filter(
                participant=self.participant
            ).values_list("id", flat=True),
        }

        response = self.client.get(self.url, data)
        self.assertQuerysetEqual(
            response.context["certifications"].order_by("id"),
            CertProjectActivity.objects.filter(id__in=certs).order_by("id"),
        )

    def test_experiences_are_chronological(self):
        self.client.force_login(self.user)
        participant = Participant.objects.filter(name="Jeff Stock").first()

        query_pararms = {
            "sections": [v for v, k in ResumeSections.choices],
            "bullets_content": ResumeFormatChoices.CHRONOLOGICAL,
            "resume_template": ResumeCoreTemplates.STANDARD,
            "preview": True,
            "experiences": Experience.objects.filter(
                participant=participant
            ).values_list("id", flat=True),
        }

        response = self.client.get(self.url, query_pararms)

        experiences = list(response.context["chronological_experiences"])
        for i, ex in enumerate(experiences[:-1]):
            self.assertGreater(
                ex["obj"].start_date, experiences[i + 1]["obj"].start_date
            )
