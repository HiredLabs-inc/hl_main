import json
import logging
import subprocess

from django.conf import settings
from django.db import transaction
from django.http import Http404
from google.auth.transport.requests import Request
from google.cloud import tasks_v2
from google.oauth2 import id_token

from .models import Task

logger = logging.getLogger(__name__)

TASK_ID_HEADER = "X-Task-Id"


def get_client():
    return tasks_v2.CloudTasksClient()


def make_cloud_task(task: Task):
    return tasks_v2.Task(
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=f"{settings.CLOUDRUN_WORKER_URL}{task.target_path}",
            headers={
                "Content-type": "application/json",
                TASK_ID_HEADER: str(task.id),
            },
            # body=json.dumps(task.payload).encode() if task.payload else None,
            oidc_token=tasks_v2.OidcToken(
                service_account_email=settings.GCP_SERVICE_ACCOUNT,
                audience=settings.CLOUDRUN_WORKER_URL,
            ),
        ),
    )


def is_authorized_task_request(request):
    """Check the OIDC token Cloud Tasks attaches (see make_cloud_task).
    Locally, tasks are posted by the send_task_request command without a token."""
    if settings.DEBUG or not settings.PRODUCTION:
        return True

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    # Tasks queued before the audience was set carry the full target URL instead
    audiences = [settings.CLOUDRUN_WORKER_URL, f"{settings.CLOUDRUN_WORKER_URL}{request.path}"]
    try:
        claims = id_token.verify_oauth2_token(
            auth_header.removeprefix("Bearer "), Request(), audience=audiences
        )
    except ValueError:
        logger.warning("Rejected task request with an invalid OIDC token")
        return False
    return claims.get("email") == settings.GCP_SERVICE_ACCOUNT and claims.get("email_verified", False)


@transaction.atomic
def work_task(request, task_func):
    """Run the Task named by the X-Task-Id header and return it with its outcome.

    Raises Http404 for a missing or unknown task. An error from task_func is
    recorded on the task and logged rather than raised; the caller answers a
    failed task with a 5xx so Cloud Tasks retries it (the queue allows 3
    attempts, see infra/terraform/modules/hl-env)."""
    task_id = request.headers.get(TASK_ID_HEADER, "")
    if not task_id.isdigit():
        raise Http404("Unknown task")

    # Lock only while marking the task as started, not while it runs
    with transaction.atomic():
        task = Task.objects.select_for_update().filter(id=task_id).first()
        if task is None:
            raise Http404("Unknown task")
        task.start()

    try:
        result = task_func(**task.payload)
    except Exception as e:
        logger.exception("Task %s failed", task.id)
        task.refresh_from_db()
        task.fail(str(e))
    else:
        task.complete(str(result))
    return task


def queue_task(target_path: str, task_data: dict):
    task = Task.objects.create(
        target_path=target_path,
        payload=task_data,
    )
    assigned_id = send_task_to_queue(task)
    task.assigned_id = assigned_id
    task.save()
    return task


def send_task_to_queue(task: Task):
    if settings.DEBUG or not settings.PRODUCTION:
        subprocess.Popen(["python", "manage.py", "send_task_request", str(task.id)])
        return task.id
    client = get_client()
    cloud_task = make_cloud_task(task)
    queued_task = client.create_task(
        tasks_v2.CreateTaskRequest(
            parent=client.queue_path(
                project=settings.GCP_PROJECT_ID,
                location=settings.GCP_REGION,
                queue=settings.GCP_TASK_QUEUE,
            ),
            task=cloud_task,
        )
    )

    # last part of the name is the task id
    return queued_task.name.split("/")[-1]


def delete_task(task):
    if settings.PRODUCTION and not settings.DEBUG:
        client = get_client()
        task_path = client.task_path(
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_REGION,
            queue=settings.GCP_TASK_QUEUE,
            task=task.assigned_id,
        )

        client.delete_task(
            tasks_v2.DeleteTaskRequest(
                name=task_path,
            )
        )

    return True
