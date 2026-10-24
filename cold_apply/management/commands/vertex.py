from django.core.management import BaseCommand

from hlagents.completion import complete
from hlagents.models import TaskConfig

TASK = "resume_overview"


class Command(BaseCommand):
    help = "Smoke test for resume text generation: one call to the resume overview task's provider and model."

    def handle(self, *args, **options):
        task = TaskConfig.objects.select_related("provider").get(key=TASK)
        self.stdout.write(f"{task}: {task.provider} · {task.model}")
        self.stdout.write(complete(TASK, "Job title: Software Engineer"))
        call = task.calls.first()
        self.stdout.write(f"{call.input_tokens} tokens in, {call.output_tokens} out, ${call.cost}")
