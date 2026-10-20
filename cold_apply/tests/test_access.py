from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from background_tasks.models import Task
from cold_apply.models import Job
from cold_apply.tests.factories import (
    BulletFactory,
    ExperienceFactory,
    JobFactory,
    ParticipantFactory,
    PositionFactory,
    UserFactory,
)
from resume.models import Bullet, Concentration, Degree, Education, Experience, Overview


def make_participant():
    return ParticipantFactory(jobs=[], experiences=[])


class ColdApplyAccessTest(TestCase):
    """Participants may only reach their own records; staff can reach everyone's."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = UserFactory(is_staff=True)
        cls.owner = make_participant()
        cls.other = make_participant()

        cls.job = JobFactory(participant=cls.owner)
        cls.experience = ExperienceFactory(participant=cls.owner, bullets=[])
        cls.bullet = BulletFactory(experience=cls.experience)
        cls.overview = Overview.objects.create(participant=cls.owner, title=cls.job.title, text="Summary")

    def owner_urls(self):
        """URLs that expose or change the owner's data (method, url)."""
        p, j, b = self.owner.pk, self.job.pk, self.bullet.pk
        return [
            ("get", reverse("cold_apply:participant_detail", args=[p])),
            ("get", reverse("cold_apply:create_job", args=[p])),
            ("get", reverse("cold_apply:participant_experience_list", args=[p])),
            ("get", reverse("cold_apply:participant_experience_by_skill_list", args=[p])),
            ("get", reverse("cold_apply:create_experience", args=[p])),
            ("get", reverse("cold_apply:create_education", args=[p])),
            ("get", reverse("cold_apply:create_bullet", args=[p])),
            ("get", reverse("cold_apply:find_new_jobs", args=[p])),
            ("get", reverse("cold_apply:job_detail", args=[j])),
            ("get", reverse("cold_apply:update_job", args=[j])),
            ("post", reverse("cold_apply:refresh_keywords", args=[j])),
            ("post", reverse("cold_apply:delete_job", args=[j])),
            ("post", reverse("cold_apply:job_status_update_modal", args=[j])),
            ("get", reverse("cold_apply:configure_tailored_resume", args=[j])),
            ("get", reverse("cold_apply:tailored_resume", args=[j])),
            ("get", reverse("cold_apply:update_experience", args=[self.experience.pk])),
            ("post", reverse("cold_apply:delete_experience", args=[self.experience.pk])),
            ("get", reverse("cold_apply:bullet_detail", args=[b])),
            ("get", reverse("cold_apply:update_bullet", args=[b])),
            ("post", reverse("cold_apply:delete_bullet", args=[b])),
            ("post", reverse("cold_apply:regenerate_bullet", args=[b, j])),
            ("get", reverse("cold_apply:overview_detail", args=[self.overview.pk])),
            ("get", reverse("cold_apply:update_overview", args=[self.overview.pk])),
            ("post", reverse("cold_apply:delete_overview", args=[self.overview.pk])),
        ]

    def staff_only_urls(self):
        return [
            reverse("cold_apply:index"),
            reverse("cold_apply:process"),
            reverse("cold_apply:update_participant", args=[self.owner.pk]),
            reverse("cold_apply:update_company", args=[self.job.company.pk]),
            reverse("cold_apply:update_title", args=[self.job.title.pk]),
            reverse("staff"),
            reverse("userprofile:veteran_status_update_view", args=[self.owner.user.pk]),
        ]

    def test_anonymous_is_sent_to_login(self):
        for method, url in self.owner_urls():
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("account_login"), response["Location"])

    def test_other_participant_gets_404(self):
        self.client.force_login(self.other.user)
        for method, url in self.owner_urls():
            with self.subTest(url=url):
                self.assertEqual(getattr(self.client, method)(url).status_code, 404)
        # Nothing was changed or deleted along the way
        self.assertTrue(Job.objects.filter(pk=self.job.pk).exists())
        self.assertTrue(Bullet.objects.filter(pk=self.bullet.pk).exists())
        self.assertTrue(Experience.objects.filter(pk=self.experience.pk).exists())
        self.assertTrue(Overview.objects.filter(pk=self.overview.pk).exists())

    def test_non_staff_cannot_reach_staff_pages(self):
        self.client.force_login(self.owner.user)
        for url in self.staff_only_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_anonymous_staff_pages_redirect_to_login(self):
        for url in self.staff_only_urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("account_login"), response["Location"])

    def test_owner_and_staff_can_open_participant_pages(self):
        for user in (self.owner.user, self.staff):
            self.client.force_login(user)
            for name in ("participant_detail", "participant_experience_list", "create_job"):
                with self.subTest(user=user.email, page=name):
                    url = reverse(f"cold_apply:{name}", args=[self.owner.pk])
                    self.assertEqual(self.client.get(url).status_code, 200)

    def test_staff_can_open_staff_pages(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("staff")).status_code, 200)
        self.assertRedirects(self.client.get(reverse("cold_apply:index")), reverse("staff"))

    def test_owner_can_delete_own_bullet(self):
        self.client.force_login(self.owner.user)
        response = self.client.post(reverse("cold_apply:delete_bullet", args=[self.bullet.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Bullet.objects.filter(pk=self.bullet.pk).exists())

    def test_staff_can_delete_any_job(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("cold_apply:delete_job", args=[self.job.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Job.objects.filter(pk=self.job.pk).exists())

    def test_regenerate_bullet_rejects_get(self):
        self.client.force_login(self.owner.user)
        url = reverse("cold_apply:regenerate_bullet", args=[self.bullet.pk, self.job.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_destructive_views_reject_get(self):
        self.client.force_login(self.owner.user)
        education = Education.objects.create(
            participant=self.owner,
            org=self.job.company,
            degree=Degree.objects.create(name="Bachelor of Science", abbr="BS"),
            concentration=Concentration.objects.create(name="History"),
        )
        urls = [
            reverse("cold_apply:refresh_keywords", args=[self.job.pk]),
            reverse("cold_apply:delete_job", args=[self.job.pk]),
            reverse("cold_apply:delete_experience", args=[self.experience.pk]),
            reverse("cold_apply:delete_education", args=[education.pk]),
            reverse("cold_apply:delete_bullet", args=[self.bullet.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
        self.assertTrue(Job.objects.filter(pk=self.job.pk).exists())
        self.assertTrue(Experience.objects.filter(pk=self.experience.pk).exists())
        self.assertTrue(Education.objects.filter(pk=education.pk).exists())
        self.assertTrue(Bullet.objects.filter(pk=self.bullet.pk).exists())

    def test_home_sends_participant_to_their_page(self):
        self.client.force_login(self.owner.user)
        response = self.client.get(reverse("cold_apply:home"))
        self.assertRedirects(
            response, reverse("cold_apply:participant_detail", args=[self.owner.pk]), fetch_redirect_response=False
        )

    def test_home_sends_user_without_participant_to_user_home(self):
        self.client.force_login(UserFactory())
        response = self.client.get(reverse("cold_apply:home"))
        self.assertRedirects(response, reverse("userprofile:user_home"), fetch_redirect_response=False)


class OverviewDeleteTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_participant()
        cls.job = JobFactory(participant=cls.owner)

    def test_redirects_to_tailored_resume_for_matching_job(self):
        overview = Overview.objects.create(participant=self.owner, title=self.job.title, text="Summary")
        self.client.force_login(self.owner.user)
        response = self.client.post(reverse("cold_apply:delete_overview", args=[overview.pk]))
        self.assertRedirects(
            response, reverse("cold_apply:configure_tailored_resume", args=[self.job.pk]), fetch_redirect_response=False
        )
        self.assertFalse(Overview.objects.filter(pk=overview.pk).exists())

    def test_redirects_to_participant_when_no_job_matches(self):
        other_title = PositionFactory()
        overview = Overview.objects.create(participant=self.owner, title=other_title, text="Summary")
        self.client.force_login(self.owner.user)
        response = self.client.post(reverse("cold_apply:delete_overview", args=[overview.pk]))
        self.assertRedirects(
            response, reverse("cold_apply:participant_detail", args=[self.owner.pk]), fetch_redirect_response=False
        )
        self.assertFalse(Overview.objects.filter(pk=overview.pk).exists())


class TaskEndpointAuthTest(TestCase):
    url = reverse("cold_apply:task_get_jobs_for_participant")

    @override_settings(DEBUG=False, PRODUCTION=True, CLOUDRUN_WORKER_URL="https://worker.example", GCP_SERVICE_ACCOUNT="tasks@x.iam")
    def test_missing_token_is_rejected(self):
        with mock.patch("cold_apply.views.work_task") as work_task:
            response = self.client.post(self.url, HTTP_X_TASK_ID="1")
        self.assertEqual(response.status_code, 403)
        work_task.assert_not_called()

    @override_settings(DEBUG=False, PRODUCTION=True, CLOUDRUN_WORKER_URL="https://worker.example", GCP_SERVICE_ACCOUNT="tasks@x.iam")
    def test_token_from_wrong_account_is_rejected(self):
        claims = {"email": "someone@else.iam", "email_verified": True}
        with mock.patch("background_tasks.queue.id_token.verify_oauth2_token", return_value=claims), \
                mock.patch("cold_apply.views.work_task") as work_task:
            response = self.client.post(self.url, HTTP_AUTHORIZATION="Bearer t", HTTP_X_TASK_ID="1")
        self.assertEqual(response.status_code, 403)
        work_task.assert_not_called()

    @override_settings(DEBUG=False, PRODUCTION=True, CLOUDRUN_WORKER_URL="https://worker.example", GCP_SERVICE_ACCOUNT="tasks@x.iam")
    def test_valid_token_runs_task(self):
        claims = {"email": "tasks@x.iam", "email_verified": True}
        with mock.patch("background_tasks.queue.id_token.verify_oauth2_token", return_value=claims) as verify, \
                mock.patch("cold_apply.views.work_task") as work_task:
            work_task.return_value.status = "success"
            work_task.return_value.has_failed.return_value = False
            response = self.client.post(self.url, HTTP_AUTHORIZATION="Bearer t", HTTP_X_TASK_ID="1")
        self.assertEqual(response.status_code, 200)
        work_task.assert_called_once()
        self.assertIn("https://worker.example", verify.call_args.kwargs["audience"])

    def test_get_is_rejected(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_failed_task_is_500_so_cloud_tasks_retries(self):
        task = Task.objects.create(target_path=self.url, payload={})
        with mock.patch("cold_apply.views.get_jobs_for_participant", side_effect=RuntimeError("scrape failed")), \
                self.assertLogs("background_tasks.queue", level="ERROR"):
            response = self.client.post(self.url, HTTP_X_TASK_ID=str(task.id))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"status": "failure"})

    def test_successful_task_is_200(self):
        task = Task.objects.create(target_path=self.url, payload={})
        with mock.patch("cold_apply.views.get_jobs_for_participant", return_value="ok"):
            response = self.client.post(self.url, HTTP_X_TASK_ID=str(task.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success"})

    def test_unknown_task_is_404(self):
        self.assertEqual(self.client.post(self.url, HTTP_X_TASK_ID="999").status_code, 404)
