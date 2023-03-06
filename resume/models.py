from django.db import models


class Overview(models.Model):  # TODO: Restructure to be more ForeignKey on Position
    TITLE_CHOICES = [
        ('Program Manager', 'Program Manager'),
        ('Sales Engineer', 'Sales Engineer'),
        ('NLP Developer', 'NLP Developer'),
    ]
    text = models.TextField()
    title = models.CharField(max_length=20, choices=TITLE_CHOICES, unique=True)

    def __str__(self):
        return self.title


class Organization(models.Model):
    ORG_TYPES = [
        ('Work', 'Work'),
        ('Edu', 'Edu'),
        ('Activity', 'Activity'),
    ]
    chronological_order = models.IntegerField(default=0)
    org_type = models.CharField(max_length=20, choices=ORG_TYPES, default=None, null=True)
    name = models.CharField(max_length=250)
    website = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.name}'


class Position(models.Model):
    title = models.CharField(max_length=50)

    def __str__(self):
        return self.title


class Degree(models.Model):
    name = models.CharField(max_length=250)
    abbr = models.CharField(max_length=4)

    def __str__(self):
        return '{}: {}'.format(self.abbr, self.name)


class Concentration(models.Model):
    name = models.CharField(max_length=25)

    def __str__(self):
        return self.name


class Experience(models.Model):
    EXP_LABELS = [
        ('Work', 'Work'),
        ('Leadership', 'Leadership'),
    ]
    start_date = models.DateField()
    end_date = models.DateField()
    label = models.CharField(max_length=20, choices=EXP_LABELS)
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)
    position = models.ForeignKey(Position, on_delete=models.CASCADE)

    def __str__(self):
        return '{}: {}'.format(self.org, self.position)


class Bullet(models.Model):
    BULLET_TYPES = [
        ('Work', 'Work'),
        ('Summary', 'Summary')
    ]
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE)
    text = models.TextField()
    type = models.CharField(max_length=20, choices=BULLET_TYPES)

    def __str__(self):
        return '{}: {}, {}'.format(self.id, self.text, self.experience)


class Education(models.Model):
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)
    degree = models.ForeignKey(Degree, on_delete=models.CASCADE)
    concentration = models.ForeignKey(Concentration, on_delete=models.CASCADE)

    def __str__(self):
        return '{}: {}, {}'.format( \
            self.org, self.degree, self.concentration)


class CertProjectActivity(models.Model):
    OPTIONS = [
        ('Certification', 'Certification'),
        ('Project', 'Project'),
        ('Activity', 'Activity')
    ]
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)
    title = models.CharField(max_length=250)
    description = models.TextField()
    variety = models.CharField(max_length=20, choices=OPTIONS)

    def __str__(self):
        return '{}: {}, {}'.format( \
            self.org, self.title, self.description)


class LanguageFATS(models.Model):
    LANGFATS_TYPES = [
        ('Human', 'Human'),
        ('Computer', 'Computer'),
        ('Framework', 'Framework'),
        ('Ability', 'Ability'),
        ('Technology', 'Technology'),
        ('Skill', 'Skill'),
    ]
    LEVELS = [
        ('Native', 'Native'),
        ('Fluent', 'Fluent'),
        ('Intermediate', 'Intermediate'),
        ('Expert', 'Expert'),
        ('Beginner', 'Beginner'),
        ('Novice', 'Novice'),
    ]
    title = models.CharField(max_length=250)
    lang_type = models.CharField(max_length=20, choices=LANGFATS_TYPES)
    level = models.CharField(max_length=20, choices=LEVELS)

    def __str__(self):
        return '{}: {}, {}'.format( \
            self.title, self.lang_type, self.level)
