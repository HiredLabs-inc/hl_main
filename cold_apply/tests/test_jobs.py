from django.test import TestCase
from django.contrib.auth.models import User

from cold_apply.jobs import save_job_search
from cold_apply.models import Job, JobSearch, Participant


class JobSearchTestCase(TestCase):
    fixtures = ["cold_apply/fixtures/dev_data.json"]

    def test_save_job_search(self):
        scraped_jobs = [
            {
                "title": "Python Developer",
                "text": "Job description 1",
                "company_detail": "Company 1",
                "location": "London",
                "application_link": "https://www.job1.com",
                "application_agent": "Total Jobs",
                "keywords": "python,django,flask",
                "id": 1,
            },
            {
                "title": "Python Developer",
                "text": "Job description 1",
                "company_detail": "Company 1",
                "location": "London",
                "application_link": "https://www.job1.com",
                "application_agent": "Total Jobs",
                "keywords": "python,django,flask",
                "id": 2,
            },
            {
                "title": "Python Developer",
                "text": "Job description 1",
                "company": "Company 1",
                "location": "London",
                "application_link": "https://www.job1.com",
                "application_agent": "Total Jobs",
                "keywords": "python,django,flask",
                "id": 3,
            },
        ]

        run_by = User.objects.get(username="admin")
        participant = Participant.objects.first()

        save_job_search(
            run_by,
            participant,
            search_query="python developer london",
            scraped_jobs=scraped_jobs,
        )

        job_search_qs = JobSearch.objects.filter(participant=participant)
        job_search = job_search_qs.first()
        self.assertEqual(job_search_qs.count(), 1)
        self.assertQuerysetEqual(
            job_search.jobs.all().order_by("id"),
            Job.objects.filter(
                participant=participant, source_id__in=[1, 2, 3]
            ).order_by("id"),
        )

    def test_doesnt_add_duplicates_but_saves_json(self):
        scraped_jobs = [
            {
                "title": "Python Developer",
                "text": "Job description 2",
                "company_detail": "Company 2",
                "location": "London",
                "application_link": "https://www.job1.com",
                "application_agent": "Total Jobs",
                "keywords": "python,django,flask",
                "id": 1,
            },
            {
                "title": "Python Developer",
                "text": "Job description 3",
                "company_detail": "Company 3",
                "location": "London",
                "application_link": "https://www.job1.com",
                "application_agent": "Total Jobs",
                "keywords": "python,django,flask",
                "id": 2,
            },
        ]

        run_by = User.objects.get(username="admin")
        participant = Participant.objects.first()

        save_job_search(
            run_by,
            participant,
            search_query="python developer london",
            scraped_jobs=scraped_jobs,
        )
        save_job_search(
            run_by,
            participant,
            search_query="python developer london",
            scraped_jobs=[
                *scraped_jobs,
                {
                    "title": "Python Developer",
                    "text": "Job description 3",
                    "company_detail": "Company 3",
                    "location": "London",
                    "application_link": "https://www.job1.com",
                    "application_agent": "Total Jobs",
                    "keywords": "python,django,flask",
                    "id": 3,
                },
            ],
        )

        job_search = (
            JobSearch.objects.filter(participant=participant)
            .order_by("-created_at")
            .first()
        )
        expected_job_count = 3

        self.assertEqual(job_search.duplicate_count, len(scraped_jobs))
        self.assertEqual(job_search.duplicates_json, scraped_jobs)
        self.assertEqual(
            Job.objects.filter(participant=participant).exclude(source_id="").count(),
            expected_job_count,
        )
