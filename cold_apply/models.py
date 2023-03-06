from django.contrib.auth.models import User
from django.db import models

from resume.models import Organization, Overview, Position, Degree, Concentration, Experience, Bullet, Education, \
    CertProjectActivity, LanguageFATS


# Create your models here.

class Participant(models.Model):
    PHASES = [
        ('PHASE_1', 'PHASE_1'),
        ('PHASE_2', 'PHASE_2'),
        ('PHASE_3', 'PHASE_3'),
        ('PHASE_4', 'PHASE_4'),
        ('PHASE_5', 'PHASE_5'),
    ]
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    uploaded_resume = models.FileField(upload_to='resumes/', blank=True, null=True)
    veteran = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    current_phase = models.CharField(max_length=20, choices=PHASES, default='PHASE_1')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='created_by', null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='updated_by', null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Participants'


class Interaction(models.Model):
    INTERACTION_TYPES = [
        ('EMAIL', 'EMAIL'),
        ('PHONE', 'PHONE'),
        ('IN_PERSON', 'IN_PERSON'),
        ('OTHER', 'OTHER'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES, default='EMAIL')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.participant}: {self.interaction_type}, {self.updated_at}'

    class Meta:
        verbose_name_plural = 'Interactions'


class Job(models.Model):
    STATUSES = [
        ('Open', 'Open'),
        ('Closed', 'Closed'),
    ]
    REASONS = [
        ('Employer Closed', 'Employer Closed'),
        ('Candidate Rejected', 'Candidate Rejected'),
    ]
    company = models.ForeignKey(Organization, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    title = models.ForeignKey(Position, on_delete=models.CASCADE)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUSES, default='Open')
    status_reason = models.CharField(max_length=20, choices=REASONS, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='job_created_by', null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='job_updated_by', null=True)

    def __str__(self):
        return f'{self.company}: {self.title}, {self.status}'

    class Meta:
        verbose_name_plural = 'Jobs'


class Application(models.Model):
    STATUSES = [
        ('Submitted', 'Submitted'),
        ('Interview', 'Interview'),
        ('Offer', 'Offer'),
        ('Rejected', 'Rejected'),
        ('Withdrawn', 'Withdrawn'),
    ]
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUSES, default='Submitted')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='application_created_by', null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='application_updated_by', null=True)

    def __str__(self):
        return f'{self.participant}: {self.job}, {self.status}'

    class Meta:
        verbose_name_plural = 'Applications'
