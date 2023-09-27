from django.core.management.base import BaseCommand, CommandError


from cold_apply.models import Applicant, Job, JobSearch, Participant


class Command(BaseCommand):
    def handle(self, *args, **options):
        pass
        # for p in Applicant.objects.all():
        #     if p.first_name == "":
        #         p.first_name = p.name.split(" ")[0]
        #         p.last_name = p.name.split(" ")[1]
        #     p.save()
        # participant = Participant.objects.get(pk=25)
        # Job.objects.get_or_create
        # participant.job_set.filter(status="New").delete()
        # get_jobs_for_participant(participant, "python developer london")
