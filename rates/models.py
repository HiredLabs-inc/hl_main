from allauth.utils import get_user_model
from django.db import models

from .choices import HDI, LEVELS, SKILL_CODES, ZONES

User = get_user_model()


class Skill(models.Model):
    name = models.CharField(max_length=50)
    base = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name_plural = "Skills"
        ordering = ["name"]


class Country(models.Model):
    rank = models.IntegerField(default=None, null=True)
    name = models.CharField(max_length=50)
    value = models.DecimalField(max_digits=8, decimal_places=3, default=0.00)
    hdi = models.CharField(max_length=10, default=None, null=True, choices=HDI)
    zone = models.CharField(max_length=1, default=None, null=True, choices=ZONES)

    class Meta:
        verbose_name_plural = "Countries"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"


class RateRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    level = models.IntegerField(choices=LEVELS)
    employer_country = models.ForeignKey(
        Country, on_delete=models.CASCADE, related_name="employer_country", default=21
    )
    worker_country = models.ForeignKey(
        Country, on_delete=models.CASCADE, related_name="worker_country"
    )
    rate = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    time_stamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.skill}, {self.level}, {self.employer_country}, {self.worker_country}, "
            f"{self.rate}, {self.time_stamp}"
        )

    class Meta:
        verbose_name_plural = "Rate Requests"
        ordering = ["-time_stamp"]


class RateResponse(models.Model):
    rate_request = models.ForeignKey(RateRequest, on_delete=models.CASCADE)
    highest_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    median_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    lowest_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.rate_request}, {self.lowest_rate}"
