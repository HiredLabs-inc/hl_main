from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404

from cold_apply.forms import ResumeConfigForm
from cold_apply.models import Job, Location, Participant, SkillBullet, State
from hl_main import settings
from cold_apply.models import Skill
from resume.models import Bullet, CertProjectActivity, Experience, Position
from resume.pdf import (
    RESUME_TEMPLATE_SECTIONS_JSON,
    ResumeCoreTemplates,
    ResumeFormatChoices,
    ResumeSections,
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
            self.assertTemplateUsed(
                response, "cold_apply/configure_tailored_resume.html"
            )
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
        response = self.client.post(self.url, data)

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
        response = self.client.post(self.url, data)
        self.assertTemplateUsed(
            response, f"resume/resume_{ResumeCoreTemplates.STANDARD}.html"
        )
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")

        self.assertEqual(response.status_code, 200)

    def test_post_request_invalid_form(self):
        self.client.force_login(self.user)
        data = {
            # Provide invalid form data here
        }
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response, "form", "bullets_content", "This field is required."
        )
        self.assertFormError(
            response, "form", "resume_template", "This field is required."
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

        response = self.client.post(self.url, data)
        self.assertQuerysetEqual(
            response.context["skills"].order_by("id"),
            Skill.objects.filter(id__in=extra_skills).order_by("id"),
        )
