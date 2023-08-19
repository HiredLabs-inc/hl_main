from allauth.utils import get_user_model
from django.db import models

User = get_user_model()


class App(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField()

    def __str__(self):
        return self.name


# Create your models here.
class Release(models.Model):
    title = models.CharField(max_length=50)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    app = models.ForeignKey(App, on_delete=models.CASCADE)
    major = models.IntegerField()
    minor = models.IntegerField()
    patch = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("app", "major", "minor", "patch")
        ordering = ["-major", "-minor", "-patch"]

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"


class Note(models.Model):
    release = models.ForeignKey(Release, on_delete=models.CASCADE)
    text = models.TextField()

    def __str__(self):
        return f"{self.release_id}: {self.text}"


class Feedback(models.Model):
    STATUSES = [
        ("Unread", "Unread"),
        ("Read", "Read"),
        ("Added to Backlog", "Added to Backlog"),
        ("Added to Roadmap", "Added to Roadmap"),
        ("Resolved", "Resolved"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    app = models.ForeignKey(App, on_delete=models.CASCADE)
    short_description = models.CharField(max_length=50)
    text = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUSES, default="Unread")

    def __str__(self):
        return self.short_description
