from django.db import models
from django.urls import reverse


class Overview(models.Model):
    text = models.TextField()
    title = models.ForeignKey(
        "Position", on_delete=models.CASCADE, default=None, null=True
    )
    participant = models.ForeignKey("cold_apply.Participant", on_delete=models.CASCADE)

    def get_absolute_url(self):
        return reverse("cold_apply:overview_detail", kwargs={"pk": self.pk})

    def __str__(self):
        return self.title.title


class Organization(models.Model):
    ORG_TYPES = [
        ("Work", "Work"),
        ("Edu", "Edu"),
        ("Activity", "Activity"),
    ]
    org_type = models.CharField(
        max_length=20, choices=ORG_TYPES, blank=True, default="Work"
    )
    name = models.CharField(max_length=250, unique=True)
    website = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name_plural = "Organizations"
        ordering = ["name"]


class Position(models.Model):
    title = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"{self.title}"

    class Meta:
        verbose_name_plural = "Positions"
        ordering = ["title"]


class Degree(models.Model):
    name = models.CharField(max_length=250)
    abbr = models.CharField(max_length=20)

    def __str__(self):
        return "{}: {}".format(self.abbr, self.name)


class Concentration(models.Model):
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name


class Experience(models.Model):
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)
    position = models.ForeignKey(Position, on_delete=models.CASCADE)
    participant = models.ForeignKey("cold_apply.Participant", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.org}: {self.position}, {self.start_date} - {self.end_date or 'Present'}"

    class Meta:
        ordering = ["-start_date"]


class Bullet(models.Model):
    BULLET_TYPES = [("Work", "Work"), ("Summary", "Summary")]
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE)
    text = models.TextField()
    type = models.CharField(max_length=20, choices=BULLET_TYPES)
    skills = models.ManyToManyField(
        to="cold_apply.Skill", through="cold_apply.SkillBullet", blank=True
    )

    def __str__(self):
        return "{}: {}, {}".format(self.id, self.text, self.experience)


class Education(models.Model):
    class EducationStatus(models.TextChoices):
        COMPLETED = "completed", "Coursework Completed"
        IN_PROGRESS = "in_progress", "In Progress"

    org = models.ForeignKey(Organization, on_delete=models.CASCADE)
    degree = models.ForeignKey(Degree, on_delete=models.CASCADE)
    concentration = models.ForeignKey(Concentration, on_delete=models.CASCADE)
    participant = models.ForeignKey("cold_apply.Participant", on_delete=models.CASCADE)
    status = models.CharField(
        choices=EducationStatus.choices,
        default=EducationStatus.COMPLETED,
        max_length=50,
    )

    def get_status_display(self):
        return (
            f"(in progress)" if self.status == self.EducationStatus.IN_PROGRESS else ""
        )

    def __str__(self):
        return "{}: {}, {}".format(self.org, self.degree, self.concentration)


class CertProjectActivity(models.Model):
    OPTIONS = [
        ("Certification", "Certification"),
        ("Project", "Project"),
        ("Activity", "Activity"),
        ("Award", "Award"),
    ]
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)
    title = models.CharField(max_length=250)
    description = models.TextField()
    variety = models.CharField(max_length=20, choices=OPTIONS)
    participant = models.ForeignKey(
        "cold_apply.Participant", on_delete=models.CASCADE, null=True
    )

    def __str__(self):
        return f"{self.org}: {self.title}"


class LanguageFATS(models.Model):
    LANGFATS_TYPES = [
        ("Human", "Human"),
        ("Computer", "Computer"),
        ("Framework", "Framework"),
        ("Ability", "Ability"),
        ("Technology", "Technology"),
        ("Skill", "Skill"),
    ]
    LEVELS = [
        ("Native", "Native"),
        ("Fluent", "Fluent"),
        ("Intermediate", "Intermediate"),
        ("Expert", "Expert"),
        ("Beginner", "Beginner"),
        ("Novice", "Novice"),
    ]
    title = models.CharField(max_length=250)
    lang_type = models.CharField(max_length=20, choices=LANGFATS_TYPES)
    level = models.CharField(max_length=20, choices=LEVELS)

    def __str__(self):
        return "{}: {}, {}".format(self.title, self.lang_type, self.level)
