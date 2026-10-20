from django import forms
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from cold_apply.models import Participant
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
        "ServicePackage", on_delete=models.SET_NULL, null=True, default=None
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
    service_doc = models.FileField(upload_to="service_docs/", default=None, null=True)
    bootcamp = models.BooleanField(default=False)

    class Meta:
        permissions = [
            ("review_veteran_status", "Can review veteran status and open service documents"),
        ]

    def handle_onboard_complete(self):
        from .intake import start_intake  # imports allauth via guards; not safe while models load

        self.is_onboarded = True
        # The jobs and resume tools hang off Participant
        Participant.objects.get_or_create(user=self.user)
        start_intake(self.user, is_veteran=self.is_veteran is not False)
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
    service_doc = models.FileField(upload_to="service_docs/", null=True)

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

class PendingSignup(models.Model):
    """An email address that started signup. The User is created only when the
    emailed link is followed and a password is set (see userprofile/signup.py)."""

    email = models.EmailField(max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    send_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.email

class OnboardingReminder(models.Model):
    """Reminders sent to a user who has an account but hasn't finished onboarding
    (see userprofile/reminders.py)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    sent_count = models.PositiveIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.user.email} ({self.sent_count})"


class BootCampSession(models.Model):
    """A scheduled coding boot camp cohort. The public site shows the next start
    date on or after today, and "dates to be announced" when there is none."""

    start_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    # Boot Camp enrollments with a seat; an enrollment without one is on the waitlist
    enrollments = models.ManyToManyField(
        "pipeline.Enrollment", through="BootCampSeat", related_name="bootcamp_sessions", blank=True
    )

    class Meta:
        ordering = ["start_date"]

    def __str__(self) -> str:
        return f"Boot camp starting {self.start_date.isoformat()}"

    @property
    def label(self) -> str:
        return f"Starts {self.start_date:%b} {self.start_date.day}, {self.start_date.year}"

    @classmethod
    def next_session(cls):
        return cls.objects.filter(start_date__gte=timezone.localdate()).order_by("start_date").first()


class BootCampSeat(models.Model):
    """A Boot Camp enrollment's place in a session: at most one per enrollment.
    Kept here rather than in pipeline so pipeline knows nothing about boot camps."""

    session = models.ForeignKey(BootCampSession, on_delete=models.PROTECT, related_name="seats")
    enrollment = models.OneToOneField("pipeline.Enrollment", on_delete=models.CASCADE, related_name="bootcamp_seat")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.enrollment.person} in {self.session}"
