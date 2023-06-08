from django.core.management.base import BaseCommand, CommandError
from cold_apply.jobs import get_jobs_for_participant, q_test_job_task


from cold_apply.models import Job, Participant


class Command(BaseCommand):
    def handle(self, *args, **options):
        q_test_job_task(30)

        # participant = Participant.objects.get(pk=25)
        # Job.objects.get_or_create
        # participant.job_set.filter(status="New").delete()
        # get_jobs_for_participant(participant, "python developer london")
