from django.db import models


class TaskStatusChoices(models.TextChoices):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"


class Task(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_id = models.CharField(max_length=36, blank=True)
    target_path = models.CharField(max_length=255)
    status = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(null=True)
    result = models.TextField()

    def has_failed(self):
        return self.status == TaskStatusChoices.FAILURE

    def in_progress(self):
        return self.status in [
            TaskStatusChoices.RUNNING,
            TaskStatusChoices.QUEUED,
        ]

    def start(self):
        self.status = TaskStatusChoices.RUNNING
        self.save()

    def fail(self, error_message):
        self.status = TaskStatusChoices.FAILURE
        self.result = error_message
        self.save()

    def complete(self, result):
        self.status = TaskStatusChoices.SUCCESS
        self.result = result
        self.save()
