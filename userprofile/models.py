from django import forms
from django.contrib.auth.models import User
from django.db import models

from cold_apply.models import Participant, Step
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
    state = models.CharField(max_length=2)
    city = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=200)
    linkedin = models.URLField(max_length=200, blank=True)

    service_package = models.ForeignKey(
        "ServicePackage", on_delete=models.SET_NULL, null=True
    )
    is_veteran = models.BooleanField(null=True)
    veteran_verified = models.BooleanField(default=False)
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

    def decrement_step(self, current_step=None):
        if current_step is None:
            current_step = self.onboarding_step
        if current_step == OnboardingStep.PROFILE:
            return False

        if current_step == OnboardingStep.VETERAN_PROFILE:
            self.onboarding_step = OnboardingStep.PROFILE

        elif current_step == OnboardingStep.UPLOAD_RESUME:
            if self.is_veteran:
                self.onboarding_step = OnboardingStep.VETERAN_PROFILE
            else:
                self.onboarding_step = OnboardingStep.PROFILE

        elif current_step == OnboardingStep.SERVICE_PACKAGE:
            self.onboarding_step = OnboardingStep.UPLOAD_RESUME

        elif current_step == OnboardingStep.COMPLETE:
            self.onboarding_step = OnboardingStep.SERVICE_PACKAGE

        self.save()
        return True

    def increment_step(self, current_step=None):
        if current_step is None:
            current_step = self.onboarding_step

        if current_step == OnboardingStep.PROFILE:
            if self.is_veteran:
                self.onboarding_step = OnboardingStep.VETERAN_PROFILE
            else:
                self.onboarding_step = OnboardingStep.SERVICE_PACKAGE

        elif current_step == OnboardingStep.VETERAN_PROFILE:
            self.onboarding_step = OnboardingStep.UPLOAD_RESUME

        elif current_step == OnboardingStep.UPLOAD_RESUME:
            self.onboarding_step = OnboardingStep.SERVICE_PACKAGE

        elif current_step == OnboardingStep.SERVICE_PACKAGE:
            self.onboarding_step = OnboardingStep.COMPLETE
            return self.handle_onboard_complete()

        return self.save()

    def handle_onboard_complete(self):
        self.is_onboarded = True
        step = Step.objects.order_by("phase__order", "order").first()

        participant, _ = Participant.objects.get_or_create(
            user=self.user, current_step=step
        )

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

    def __str__(self) -> str:
        return self.name
