# Generated by Django 4.2.2 on 2023-06-07 20:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cold_apply', '0024_job_application_agent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='application_link',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='job',
            name='source_link',
            field=models.URLField(blank=True, max_length=500),
        ),
    ]