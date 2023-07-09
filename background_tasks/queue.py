import json
import subprocess

from django.conf import settings
from django.db import transaction
from google.cloud import tasks_v2

from .models import Task

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
            ),
        ),
    )


@transaction.atomic
def work_task(request, task_func):
    """Simple implementation, need to improve later"""
    assigned_id = request.headers.get("X-Cloudtasks-Taskname")
    task_id = request.headers.get("X-Task-Id")
    task = Task.objects.filter(id=task_id).select_for_update().first()
    task.start()
    try:
        result = task_func(**task.payload)
        task.complete(str(result))
        return result
    except Exception as e:
        task.refresh_from_db()
        task.fail(str(e))


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
