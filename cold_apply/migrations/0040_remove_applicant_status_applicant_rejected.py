# Generated by Django 4.2.2 on 2023-06-14 17:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cold_apply', '0039_alter_applicant_status_alter_participant_applicant'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='applicant',
            name='status',
        ),
        migrations.AddField(
            model_name='applicant',
            name='rejected',
            field=models.BooleanField(default=False),
        ),
    ]