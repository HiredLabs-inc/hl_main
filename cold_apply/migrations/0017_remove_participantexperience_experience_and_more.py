# Generated by Django 4.2 on 2023-05-24 20:22

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cold_apply', '0016_alter_applicant_location'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='participantexperience',
            name='experience',
        ),
        migrations.RemoveField(
            model_name='participantexperience',
            name='participant',
        ),
        migrations.RemoveField(
            model_name='participantoverview',
            name='overview',
        ),
        migrations.RemoveField(
            model_name='participantoverview',
            name='participant',
        ),
        migrations.DeleteModel(
            name='ParticipantEducation',
        ),
        migrations.DeleteModel(
            name='ParticipantExperience',
        ),
        migrations.DeleteModel(
            name='ParticipantOverview',
        ),
    ]