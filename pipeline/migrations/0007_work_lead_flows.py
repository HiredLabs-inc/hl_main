"""pipeline.work_lead_flows, given to the Agents group so volunteers in it can
work the Funding and Outreach boards (docs/designs/in-progress/volunteer-logins.md §3.3). Staff pass
through is_staff, so nothing changes for them."""
from django.contrib.auth.management import create_permissions
from django.db import migrations

AGENTS_GROUP = "Agents"


def add_to_agents(apps, schema_editor):
    # Permissions are normally created after all migrations run; create them now
    app_config = apps.get_app_config("pipeline")
    app_config.models_module = True
    create_permissions(app_config, apps=apps, verbosity=0)
    app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    group, _ = Group.objects.get_or_create(name=AGENTS_GROUP)
    group.permissions.add(Permission.objects.get(codename="work_lead_flows", content_type__app_label="pipeline"))


def remove_from_agents(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    Permission.objects.filter(codename="work_lead_flows", content_type__app_label="pipeline").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("hlagents", "0004_agents_group"),
        ("pipeline", "0006_lead_enrollments"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="enrollment",
            options={"permissions": [("work_lead_flows", "Can view and work Funding and Outreach enrollments")]},
        ),
        migrations.RunPython(add_to_agents, remove_from_agents),
    ]
