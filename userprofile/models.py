from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nickname = models.CharField(max_length=300)

    def __str__(self):
        return '{}: {}, AKA: {}'\
        .format(\
        self.user.id,
        self.user.get_full_name(),
        self.nickname,
        )
