# Generated by Django 4.2.2 on 2024-03-15 17:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('userprofile', '0013_remove_profile_onboarding_step'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='bootcamp',
            field=models.BooleanField(default=False),
        ),
    ]