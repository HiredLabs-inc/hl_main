from django.contrib.auth.models import User
from django.db import models


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
        unique_together = ('app', 'major', 'minor', 'patch')
        ordering = ['-major', '-minor', '-patch']

    def __str__(self):
        return f'{self.major}.{self.minor}.{self.patch}'


class Note(models.Model):
    release = models.ForeignKey(Release, on_delete=models.CASCADE)
    text = models.TextField()

    def __str__(self):
        return self.text


class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    app = models.ForeignKey(App, on_delete=models.CASCADE)
    text = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text
