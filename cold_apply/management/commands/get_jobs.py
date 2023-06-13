from django.core.management.base import BaseCommand, CommandError
from cold_apply.jobs import get_jobs_for_participant, q_test_job_task


from cold_apply.models import Job, JobSearch, Participant


class Command(BaseCommand):
    def handle(self, *args, **options):
        search = JobSearch.objects.first()

        jobs = Job.objects.all()[:5]

        search.jobs.add(*jobs)
        search.jobs.all().delete()

        # participant = Participant.objects.get(pk=25)
        # Job.objects.get_or_create
        # participant.job_set.filter(status="New").delete()
        # get_jobs_for_participant(participant, "python developer london")
