"""The Agents group: run agents, review and edit leads, import partners
(docs/designs/completed/hlagents.md §3.5). Staff get it now; volunteers can be added once they
have logins (IDEA-005). Changing agent settings (H3) isn't included.
"""
from django.contrib.auth.management import create_permissions
from django.db import migrations

AGENTS_GROUP = "Agents"
PERMISSIONS = ["view_agentconfig", "view_agentrun", "add_agentrun", "view_lead", "change_lead", "add_lead"]


def create_agents_group(apps, schema_editor):
    # Permissions are normally created after all migrations run; create them now
    app_config = apps.get_app_config("hlagents")
    app_config.models_module = True
    create_permissions(app_config, apps=apps, verbosity=0)
    app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("auth", "User")
    group, _ = Group.objects.get_or_create(name=AGENTS_GROUP)
    group.permissions.add(*Permission.objects.filter(content_type__app_label="hlagents", codename__in=PERMISSIONS))
    group.user_set.add(*User.objects.filter(is_staff=True, is_active=True))


def delete_agents_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name=AGENTS_GROUP).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("hlagents", "0003_lead_bounces"),
    ]

    operations = [
        migrations.RunPython(create_agents_group, delete_agents_group),
    ]
