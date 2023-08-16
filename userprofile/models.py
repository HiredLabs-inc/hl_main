from django import forms
from django.contrib.auth.models import User
from django.db import models

from hl_main.models import TrackedModel


class OnboardingStep(models.TextChoices):
    PROFILE = "PROFILE", "Profile"
    VETERAN_PROFILE = "VETERAN_PROFILE", "Veteran Status"
    SERVICE_PACKAGE = "SERVICE_PACKAGE", "Service Package"
    UPLOAD_RESUME = "UPLOAD_RESUME", "Upload Resume"
    COMPLETE = "COMPLETE", "Complete"


class Profile(TrackedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nickname = models.CharField(max_length=300)
    phone = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, null=True)
    linkedin = models.URLField(max_length=200, blank=True)

    service_package = models.ForeignKey(
        "ServicePackage", on_delete=models.SET_NULL, null=True
    )
    is_veteran = models.BooleanField(null=True)
    is_onboarded = models.BooleanField(default=False)
    resume = models.FileField(upload_to="uploads/", null=True)

    special_training = models.TextField(blank=True, null=True)
    special_skills = models.TextField(blank=True, null=True)
    job_links = models.TextField(blank=True, null=True)
    work_preferences = models.TextField(blank=True, null=True)

    onboarding_step = models.CharField(
        max_length=20, choices=OnboardingStep.choices, default=OnboardingStep.PROFILE
    )
    dnc = models.BooleanField(default=False)

    def increment_step(self):
        current = self.onboarding_step

        if current == OnboardingStep.PROFILE:
            if self.is_veteran:
                self.onboarding_step = OnboardingStep.VETERAN_PROFILE
            else:
                self.onboarding_step = OnboardingStep.SERVICE_PACKAGE

        elif current == OnboardingStep.VETERAN_PROFILE:
            self.onboarding_step = OnboardingStep.SERVICE_PACKAGE

        elif current == OnboardingStep.SERVICE_PACKAGE:
            self.onboarding_step = OnboardingStep.UPLOAD_RESUME

        elif current == OnboardingStep.UPLOAD_RESUME:
            self.onboarding_step = OnboardingStep.COMPLETE
            return self.handle_onboard_complete()

        return self.save()

    def handle_onboard_complete(self):
        self.is_onboarded = True
        # do service package stuff
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


class ServicePackage(models.Model):
    name = models.CharField(max_length=300)
