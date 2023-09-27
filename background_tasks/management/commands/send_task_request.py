import json
from django.core.management import BaseCommand
from django.core.management.base import CommandParser
import requests

from background_tasks.models import Task
from background_tasks.queue import TASK_ID_HEADER

class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("task_id", type=int, help="Task ID to send to queue")

    def handle(self, *args, **options):
        task_id = options["task_id"]
        task = Task.objects.get(id=task_id)
        requests.post(
            f"http://django-tasks:8001{task.target_path}",
            # json=task.payload,
            headers={
                "X-Cloudtasks-Taskname": str(task_id),
                "Content-type": "application/json",
                TASK_ID_HEADER: str(task_id)
            },
        )