from django import forms
from django.contrib.auth.models import User
from django.db import models

from cold_apply.models import Participant, Step
from hl_main.models import TrackedModel

class OnboardingStep(models.TextChoices):
    PROFILE = "PROFILE", "Profile"
    VETERAN_PROFILE = "VETERAN_PROFILE", "Veteran Status"
    SERVICE_PACKAGE = "SERVICE_PACKAGE", "Service Package"
    UPLOAD_SERVICE_DOC = "UPLOAD_SERVICE_DOC", "Upload Service Doc"
    UPLOAD_RESUME = "UPLOAD_RESUME", "Upload Resume"
    COMPLETE = "COMPLETE", "Complete"

class Profile(TrackedModel):
    SERVICE_BRANCHES = [
        ("ARMY", "US Army"),
        ("NAVY", "US Navy"),
        ("AIR_FORCE", "US Air Force"),
        ("MARINE CORPS", "US Marine Corps"),
        ("COAST_GUARD", "US Coast Guard"),
        ("SPACE_FORCE", "Space Force"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=200, default="None Entered")
    address = models.CharField(max_length=200, default="None Entered")
    state = models.CharField(max_length=2)
    city = models.CharField(max_length=100)
    linkedin = models.URLField(max_length=200, default="https://www.linkedin.com/")
    service_package = models.ForeignKey(
        "ServicePackage", on_delete=models.SET_NULL, null=True, default=1
    )
    is_veteran = models.BooleanField(null=True, default=True)
    veteran_verified = models.BooleanField(default=False)
    is_onboarded = models.BooleanField(default=False)
    special_training = models.TextField(blank=True, null=True)
    special_skills = models.TextField(blank=True, null=True)
    job_links = models.TextField(blank=True, null=True)
    work_preferences = models.TextField(blank=True, null=True)
    dnc = models.BooleanField(default=False)
    service_branch = models.CharField(
        max_length=200,
        choices=SERVICE_BRANCHES,
        null=True,
        default="Not a Veteran",
    )
    military_specialiaty = models.CharField(max_length=200, null=True)
    years_of_service = models.IntegerField(null=True)
    rank_at_separation = models.CharField(max_length=200, null=True)
    resume = models.FileField(upload_to="uploads/", default=None, null=True)
    service_doc = models.FileField(upload_to="uploads/", default=None, null=True)
    bootcamp = models.BooleanField(default=False)

    def handle_onboard_complete(self):
        self.is_onboarded = True
        step = Step.objects.order_by("phase__order", "order").first()

        participant, _ = Participant.objects.get_or_create(
            user=self.user, current_step=step
        )
        return self.save()

class ServiceBranches(models.TextChoices):
    ARMY = "ARMY", "Army"
    NAVY = "NAVY", "Navy"
    AIR_FORCE = "AIR_FORCE", "Air Force"
    MARINES = "MARINES", "Marines"
    COAST_GUARD = "COAST_GUARD", "Coast Guard"
    SPACE_FORCE = "SPACE_FORCE", "Space Force"

class VeteranProfile(TrackedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    service_branch = models.CharField(
        max_length=200,
        choices=ServiceBranches.choices,
        null=True,
        default="Not a Veteran",
    )
    military_specialiaty = models.CharField(max_length=200, null=True)
    years_of_service = models.IntegerField(null=True)
    rank_at_separation = models.CharField(max_length=200, null=True)
    service_doc = models.FileField(upload_to="uploads/", null=True)

class ServicePackage(models.Model):
    name = models.CharField(max_length=300)

    def __str__(self) -> str:
        return self.name

class Comment(models.Model):
    name = models.CharField(max_length=200, default="None Entered")
    email = models.EmailField(default="None Entered")
    comment = models.TextField(default="None Entered")

    def __str__(self) -> str:
        return f'{self.name}, {self.email}'
