# Generated by Django 4.2.2 on 2023-10-16 23:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('userprofile', '0007_remove_profile_service_documents_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='onboarding_step',
            field=models.CharField(choices=[('PROFILE', 'Profile'), ('VETERAN_PROFILE', 'Veteran Status'), ('SERVICE_PACKAGE', 'Service Package'), ('UPLOAD_SERVICE_DOC', 'Upload Service Doc'), ('UPLOAD_RESUME', 'Upload Resume'), ('COMPLETE', 'Complete')], default='PROFILE', max_length=20),
        ),
    ]