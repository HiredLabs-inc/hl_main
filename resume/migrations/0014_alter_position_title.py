# Generated by Django 4.2.2 on 2023-06-07 20:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resume', '0013_alter_position_title'),
    ]

    operations = [
        migrations.AlterField(
            model_name='position',
            name='title',
            field=models.CharField(max_length=100, unique=True),
        ),
    ]