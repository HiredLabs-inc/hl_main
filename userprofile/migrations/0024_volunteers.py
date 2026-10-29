"""The Volunteers group, which marks volunteers and holds no permissions, and
VolunteerInvite (docs/designs/in-progress/volunteer-logins.md §3.1, §3.4)."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

VOLUNTEERS_GROUP = "Volunteers"


def create_volunteers_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.get_or_create(name=VOLUNTEERS_GROUP)


def delete_volunteers_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name=VOLUNTEERS_GROUP).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('userprofile', '0023_bootcampseat'),
    ]

    operations = [
        migrations.CreateModel(
            name='VolunteerInvite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=150)),
                ('first_name', models.CharField(blank=True, max_length=150)),
                ('last_name', models.CharField(blank=True, max_length=150)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_sent_at', models.DateTimeField(blank=True, null=True)),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('groups', models.ManyToManyField(related_name='volunteer_invites', to='auth.group')),
                ('invited_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='volunteer_invites_sent', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='volunteer_invites_accepted', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RunPython(create_volunteers_group, delete_volunteers_group),
    ]
