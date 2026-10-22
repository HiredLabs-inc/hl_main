"""Flows people move through (Intake, Resume & Job Search, Boot Camp, ...) and each
person's place in them. Kept free of cold_apply imports so other programs can
reuse it; a person is a User.

Change enrollments only through pipeline.services, which also writes the
Activity timeline.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from hl_main.models import TrackedModel

User = settings.AUTH_USER_MODEL


class Flow(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name

    def first_step(self):
        return Step.objects.filter(phase__flow=self).first()


class Phase(models.Model):
    flow = models.ForeignKey(Flow, on_delete=models.CASCADE, related_name="phases")
    title = models.CharField(max_length=200)
    # Copied from cold_apply.Phase: what starts and ends the phase, and its result
    start = models.CharField(max_length=200, blank=True)
    end = models.CharField(max_length=200, blank=True)
    result = models.CharField(max_length=200, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["flow__order", "flow_id", "order", "id"]

    def __str__(self):
        return f"{self.flow}: {self.title}"


class Step(models.Model):
    class Owner(models.TextChoices):
        PARTICIPANT = "Participant", "Participant"
        HIRED_LABS = "Hired Labs", "Hired Labs"

    phase = models.ForeignKey(Phase, on_delete=models.CASCADE, related_name="steps")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    owner = models.CharField(max_length=20, choices=Owner.choices, default=Owner.HIRED_LABS)
    # "app_label.codename". Only users with this permission can move an
    # enrollment off this step (e.g. Verify Veteran Status).
    required_permission = models.CharField(max_length=100, blank=True)
    # A final step: enrollments can only be completed from one (e.g. Graduated)
    completes_flow = models.BooleanField(default=False)

    class Meta:
        ordering = ["phase__flow__order", "phase__flow_id", "phase__order", "phase_id", "order", "id"]

    def __str__(self):
        return f"{self.phase.title}: {self.title}"

    @property
    def flow(self):
        return self.phase.flow

    def next_step(self):
        """The step after this one in its flow, or None if it's the last"""
        steps = list(Step.objects.filter(phase__flow_id=self.phase.flow_id).values_list("pk", flat=True))
        index = steps.index(self.pk)
        return Step.objects.get(pk=steps[index + 1]) if index + 1 < len(steps) else None


class Enrollment(TrackedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        # Soft rejection (e.g. unclear DD214): undone when the person responds
        REJECTED = "rejected", "Rejected"
        NO_SHOW = "no_show", "No show"
        COMPLETED = "completed", "Completed"
        # Left before taking part (e.g. before their boot camp session started)
        WITHDRAWN = "withdrawn", "Withdrawn"
        # Took part (e.g. an active boot camp student) but didn't finish
        DROPPED = "dropped", "Dropped"

    # Statuses that close the enrollment. pipeline.services.reopen undoes them.
    ENDED_STATUSES = {Status.COMPLETED, Status.WITHDRAWN, Status.DROPPED}

    person = models.ForeignKey(User, on_delete=models.CASCADE, related_name="enrollments")
    flow = models.ForeignKey(Flow, on_delete=models.PROTECT, related_name="enrollments")
    current_step = models.ForeignKey(Step, on_delete=models.PROTECT, related_name="enrollments")
    assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_enrollments"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    step_entered_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["person", "flow"],
                condition=Q(ended_at__isnull=True),
                name="one_open_enrollment_per_flow",
            ),
        ]

    def __str__(self):
        return f"{self.person}: {self.flow} ({self.get_status_display()})"

    @property
    def is_ended(self):
        return self.ended_at is not None

    @property
    def days_in_step(self):
        return (timezone.now() - self.step_entered_at).days


class Activity(models.Model):
    class Kind(models.TextChoices):
        NOTE = "note", "Note"
        EMAIL = "email", "Email"
        PHONE = "phone", "Phone"
        IN_PERSON = "in_person", "In person"
        ENROLLED = "enrolled", "Enrolled"
        STEP_CHANGE = "step_change", "Step change"
        ASSIGNEE_CHANGE = "assignee_change", "Assignee change"
        STATUS_CHANGE = "status_change", "Status change"
        DOCUMENT_OPENED = "document_opened", "Document opened"
        SESSION_CHANGE = "session_change", "Boot camp session"

    # Kinds staff can write by hand; the rest are recorded by pipeline.services
    CONTACT_KINDS = {Kind.NOTE, Kind.EMAIL, Kind.PHONE, Kind.IN_PERSON}

    person = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities")
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, null=True, blank=True, related_name="activities"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    text = models.TextField(blank=True)
    from_value = models.CharField(max_length=200, blank=True)
    to_value = models.CharField(max_length=200, blank=True)
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities_performed"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "Activities"
        indexes = [models.Index(fields=["person", "-created_at"])]

    def __str__(self):
        return f"{self.person}: {self.get_kind_display()} ({self.created_at:%Y-%m-%d})"

    @property
    def is_contact(self):
        """Written by staff (a note or contact) rather than recorded by a change"""
        return self.kind in self.CONTACT_KINDS
