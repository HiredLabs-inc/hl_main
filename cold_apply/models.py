from django.contrib.auth.models import User
from django.db import models

from rates.models import Country
from resume.models import Bullet, Organization, Position

# Create your models here.


class Participant(models.Model):
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    dnc = models.BooleanField(default=False)
    location = models.ForeignKey(
        "Location", null=True, on_delete=models.SET_NULL
    )  # drop null later?
    uploaded_resume = models.FileField(upload_to="uploads/", blank=True, null=True)
    uploaded_resume_title = models.CharField(max_length=100, blank=True, null=True)
    veteran = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    current_step = models.ForeignKey(
        "Step", on_delete=models.SET_NULL, blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="created_by", null=True
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="updated_by", null=True
    )

    def __str__(self):
        return f"{self.name}: {self.email}"

    class Meta:
        verbose_name_plural = "Participants"
        ordering = ["-created_at"]


class Interaction(models.Model):
    INTERACTION_TYPES = [
        ("EMAIL", "EMAIL"),
        ("PHONE", "PHONE"),
        ("IN_PERSON", "IN_PERSON"),
        ("OTHER", "OTHER"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    interaction_type = models.CharField(
        max_length=20, choices=INTERACTION_TYPES, default="EMAIL"
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.participant}: {self.interaction_type}, {self.updated_at}"

    class Meta:
        verbose_name_plural = "Interactions"


# This refers to open jobs, not to jobs a participant has already had in the past
class Job(models.Model):
    STATUSES = [
        ("Open", "Open"),
        ("Closed", "Closed"),
    ]
    REASONS = [
        ("In Progress", "In Progress"),
        ("Employer Closed", "Employer Closed"),
        ("Candidate Rejected", "Candidate Rejected"),
        ("Cycle Complete", "Cycle Complete"),
    ]
    company = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True)
    participant = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True)
    title = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUSES, default="Open")
    status_reason = models.CharField(
        max_length=20, choices=REASONS, blank=True, null=True
    )
    application_link = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="job_created_by", null=True
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="job_updated_by", null=True
    )

    def __str__(self):
        return f"{self.company}: {self.title}, {self.status}: {self.participant.name}"

    class Meta:
        verbose_name_plural = "Jobs"


class Application(models.Model):
    STATUSES = [
        ("Submitted", "Submitted"),
        ("Interview", "Interview"),
        ("Offer", "Offer"),
        ("Rejected", "Rejected"),
        ("Withdrawn", "Withdrawn"),
    ]
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUSES, default="Submitted")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="application_created_by",
        null=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="application_updated_by",
        null=True,
    )

    def __str__(self):
        return f"{self.job.participant}: {self.job}, {self.status}"

    class Meta:
        verbose_name_plural = "Applications"


# cold_apply interacation Phases
class Phase(models.Model):
    title = models.CharField(max_length=200)
    start = models.CharField(max_length=200)
    end = models.CharField(max_length=200)
    result = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = "Phases"


# cold_apply interaction Phase substeps
class Step(models.Model):
    OWNER_CHOICES = [
        ("Participant", "Participant"),
        ("Hired Labs", "Hired Labs"),
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()
    phase = models.ForeignKey(Phase, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    owner = models.CharField(max_length=20, choices=OWNER_CHOICES, default="Hired Labs")

    def __str__(self):
        return f"{self.title}: {self.phase.title}"

    class Meta:
        verbose_name_plural = "Steps"


# Results of keyword analysis algorithm. There is one per job, and it is overwritten whenever a new keyword analysis
# is run.
class KeywordAnalysis(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    unigram = models.CharField(max_length=200)
    bigram = models.CharField(max_length=200)
    trigram = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.job}"

    class Meta:
        verbose_name_plural = "Keyword Analyses"


class WeightedBullet(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    position = models.ForeignKey(Position, on_delete=models.CASCADE)
    bullet = models.ForeignKey(Bullet, on_delete=models.CASCADE)
    weight = models.FloatField()

    def __str__(self):
        return f"{self.participant.name}: {self.position.title} {self.bullet.text} ({self.weight})"

    @property
    def weight_display(self):
        return f"({self.weight})"

    class Meta:
        verbose_name_plural = "Weighted Bullets"
        ordering = ["-weight"]


class BulletKeyword(models.Model):
    bullet = models.ForeignKey(Bullet, on_delete=models.CASCADE)
    unigram = models.CharField(max_length=200)
    bigram = models.CharField(max_length=200)
    trigram = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.bullet.text}: {self.unigram}, {self.bigram}, {self.trigram}"

    class Meta:
        verbose_name_plural = "Bullet Keywords"


class Skill(models.Model):
    TYPES = [
        ("Hard", "Hard"),
        ("Soft", "Soft"),
    ]
    title = models.CharField(max_length=200)
    type = models.CharField(max_length=200, choices=TYPES, default="Hard")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = "Skills"


class SkillBullet(models.Model):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    bullet = models.ForeignKey(Bullet, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.skill.title}: {self.bullet.text}"

    class Meta:
        verbose_name_plural = "Skill Bullets"


class State(models.Model):
    name = models.CharField(max_length=200)
    abbreviation = models.CharField(max_length=2)

    def __str__(self):
        return f"{self.name}, {self.abbreviation}"

    class Meta:
        verbose_name_plural = "States"


class Location(models.Model):
    city = models.CharField(max_length=200)
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.city}, {self.state.name}, {self.country.name}"

    class Meta:
        verbose_name_plural = "Locations"


class Applicant(models.Model):
    BRANCHES = [
        ("Army", "Army"),
        ("Navy", "Navy"),
        ("Air Force", "Air Force"),
        ("Marines", "Marines"),
        ("Coast Guard", "Coast Guard"),
        ("Space Force", "Space Force"),
        ("Not a Veteran", "Not a Veteran"),
    ]
    name = models.CharField(max_length=200)
    email = models.EmailField(max_length=200)
    phone = models.CharField(max_length=200)
    location = models.TextField(blank=True, null=True)
    linkedin = models.URLField(max_length=200)
    resume = models.FileField(upload_to="uploads/", blank=True, null=True)
    special_training = models.TextField(blank=True, null=True)
    special_skills = models.TextField(blank=True, null=True)
    job_links = models.TextField(blank=True, null=True)
    work_preferences = models.TextField(blank=True, null=True)
    service_branch = models.CharField(
        max_length=200, choices=BRANCHES, null=True, default="Not a Veteran"
    )
    military_specialiaty = models.CharField(max_length=200, null=True)
    years_of_service = models.IntegerField(null=True)
    rank_at_separation = models.CharField(max_length=200, null=True)
