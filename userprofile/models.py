from django import forms
from django.contrib.auth.models import User, Group
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
    # Remove
    # nickname = models.CharField(max_length=300)
    # end remove
    phone = models.CharField(max_length=200, default="None Entered")
    address = models.CharField(max_length=200, default="None Entered")
    state = models.CharField(max_length=2)
    city = models.CharField(max_length=100)
    # Remove
    # country = models.CharField(max_length=200, default="USA")
    # zip_code = models.CharField(max_length=200)
    # birthdate = models.DateField(null=True, blank=True)
    # end remove
    linkedin = models.URLField(max_length=200, default="https://www.linkedin.com/")
    # set default, will not be used for MVP immediately after, but want to keep available
    service_package = models.ForeignKey(
        "ServicePackage", on_delete=models.SET_NULL, null=True, default=1
    )
    # set default to True; will not be used for MVP immediately after, but want to keep available
    is_veteran = models.BooleanField(null=True, default=True)
    # Leave as is; Veterans still need to be verified
    veteran_verified = models.BooleanField(default=False)
    # Revisit this logic. Can be used as a flag to initiate admin steps, rather than complete signup.
    is_onboarded = models.BooleanField(default=False)

    special_training = models.TextField(blank=True, null=True)
    special_skills = models.TextField(blank=True, null=True)
    job_links = models.TextField(blank=True, null=True)
    work_preferences = models.TextField(blank=True, null=True)
    # Revisit logic.
    # possible solution:
    # ## - add an onboarding step and associated logic to increment/decrement, then set that as default
    # onboarding_step = models.CharField(
    #     max_length=20, choices=OnboardingStep.choices, default=OnboardingStep.PROFILE
    # )
    # Leave as is.
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
    # Leave optional
    resume = models.FileField(upload_to="uploads/", default=None, null=True)
    service_doc = models.FileField(upload_to="uploads/", default=None, null=True)

    # def decrement_step(self, current_step=None):
    #     if current_step is None:
    #         current_step = self.onboarding_step
    #     if current_step == OnboardingStep.PROFILE:
    #         return False
    #
    #     if current_step == OnboardingStep.VETERAN_PROFILE:
    #         self.onboarding_step = OnboardingStep.PROFILE
    #
    #     elif current_step == OnboardingStep.UPLOAD_RESUME:
    #         if self.is_veteran:
    #             self.onboarding_step = OnboardingStep.UPLOAD_SERVICE_DOC
    #         else:
    #             self.onboarding_step = OnboardingStep.PROFILE
    #
    #     elif current_step == OnboardingStep.UPLOAD_SERVICE_DOC:
    #         self.onboarding_step = OnboardingStep.VETERAN_PROFILE
    #
    #     elif current_step == OnboardingStep.SERVICE_PACKAGE:
    #         self.onboarding_step = OnboardingStep.UPLOAD_RESUME
    #
    #     elif current_step == OnboardingStep.COMPLETE:
    #         self.onboarding_step = OnboardingStep.SERVICE_PACKAGE
    #
    #     self.save()
    #     return True

    # def increment_step(self, current_step=None):
    #     if current_step is None:
    #         current_step = self.onboarding_step
    #
    #     if current_step == OnboardingStep.PROFILE:
    #         if self.is_veteran:
    #
    #             self.onboarding_step = OnboardingStep.VETERAN_PROFILE
    #         else:
    #             self.onboarding_step = OnboardingStep.UPLOAD_RESUME
    #
    #     elif current_step == OnboardingStep.VETERAN_PROFILE:
    #         self.onboarding_step = OnboardingStep.UPLOAD_SERVICE_DOC
    #
    #     elif current_step == OnboardingStep.UPLOAD_SERVICE_DOC:
    #         self.onboarding_step = OnboardingStep.UPLOAD_RESUME
    #
    #     elif current_step == OnboardingStep.UPLOAD_RESUME:
    #         self.onboarding_step = OnboardingStep.SERVICE_PACKAGE
    #
    #     elif current_step == OnboardingStep.SERVICE_PACKAGE:
    #         self.onboarding_step = OnboardingStep.COMPLETE
    #         return self.handle_onboard_complete()
    #
    #     return self.save()

    def handle_onboard_complete(self):
        self.is_onboarded = True
        step = Step.objects.order_by("phase__order", "order").first()

        participant, _ = Participant.objects.get_or_create(
            user=self.user, current_step=step
        )
        # Add to cold_apply_user group
        # Remove this, but keep the code handy for future use. This will be good for self-service, and can be used for
        #   other applications
        # group = Group.objects.get(name="cold_apply_user")
        # self.user.groups.add(group)
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
