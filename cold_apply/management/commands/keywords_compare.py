"""Compare the in-house keyword analyzer with the job_keywords task on real jobs
(docs/designs/completed/ai-tasks.md §4 K). Nothing is saved: the task calls are rolled back too.

    python manage.py keywords_compare --jobs 10 [--model gemma4:31b] [--job 12 --job 40]
"""
import time

from django.core.management.base import BaseCommand
from django.db import transaction

from cold_apply.keywords import LISTS, KeywordError, fallback_keywords, parse_reply, usable_phrases
from cold_apply.models import Job
from hlagents.completion import CompletionFailed, complete
from hlagents.models import TaskConfig

TASK = "job_keywords"


class Rollback(Exception):
    pass


class Command(BaseCommand):
    help = "Print the old and LLM keywords side by side for some jobs, without saving either."

    def add_arguments(self, parser):
        parser.add_argument("--jobs", type=int, default=10, help="How many recent jobs with a description")
        parser.add_argument("--job", type=int, action="append", help="A job id (repeatable); overrides --jobs")
        parser.add_argument("--model", help="Model to use instead of the task's (same provider)")

    def handle(self, *args, **options):
        jobs = Job.objects.exclude(description="").select_related("title", "company").order_by("-pk")
        jobs = jobs.filter(pk__in=options["job"]) if options["job"] else jobs[: options["jobs"]]
        rows = []
        try:
            with transaction.atomic():
                task = TaskConfig.objects.select_related("provider").get(key=TASK)
                if options["model"]:
                    task.model = options["model"]
                    task.save(update_fields=["model"])
                self.stdout.write(f"{task}: {task.provider} · {task.model}")
                for job in jobs:
                    rows.append(self._compare(job, task))
                raise Rollback
        except Rollback:
            pass

        self.stdout.write("\njob | words | returned (1/2/3 words) | kept | rows | seconds | tokens in, out | result")
        for row in rows:
            self.stdout.write(" | ".join(str(value) for value in row))

    def _compare(self, job, task):
        self.stdout.write(f"\n== Job {job.pk}: {job.title} at {job.company} ({len(job.description.split())} words)")
        old = fallback_keywords(job.description)
        started = time.monotonic()
        returned = kept = ""
        rows = 0
        try:
            data = parse_reply(complete(TASK, job.description))
            returned = "/".join(str(len(data.get(key) or [])) for key, _, _ in LISTS)
            new = usable_phrases(data, job.description)
            kept = "/".join(str(len(phrases)) for phrases in new.values())
            rows = max(len(phrases) for phrases in new.values())
            if not rows:
                raise KeywordError("No usable keywords in the reply.")
            result = "ok"
        except (CompletionFailed, KeywordError) as e:
            new = {field: [] for _, field, _ in LISTS}
            result = f"fallback: {e}"
        seconds = round(time.monotonic() - started, 1)

        for _, field, _ in LISTS:
            self.stdout.write(f"  {field}s")
            self.stdout.write(f"    old: {', '.join(old[field])}")
            self.stdout.write(f"    llm: {', '.join(new[field])}")
        call = task.calls.first()
        tokens = f"{call.input_tokens}, {call.output_tokens}" if call else ""
        return (job.pk, len(job.description.split()), returned, kept, rows, seconds, tokens, result)
