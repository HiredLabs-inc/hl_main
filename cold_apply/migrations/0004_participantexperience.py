# Generated by Django 4.1.7 on 2023-03-21 21:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('resume', '0003_remove_experience_label_alter_experience_end_date'),
        ('cold_apply', '0003_alter_participant_uploaded_resume'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParticipantExperience',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('experience', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='resume.experience')),
                ('participant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cold_apply.participant')),
            ],
            options={
                'verbose_name_plural': 'Participant Experiences',
            },
        ),
    ]