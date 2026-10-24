"""service_branch defaults to None, not "Not a Veteran", which isn't one of its
choices and duplicated is_veteran (BUG-032). Rows still holding the old
default have no branch, so they become None."""
from django.db import migrations, models

OLD_DEFAULT = "Not a Veteran"


def clear_old_default(apps, schema_editor):
    for model in ("Profile", "VeteranProfile"):
        apps.get_model("userprofile", model).objects.filter(service_branch=OLD_DEFAULT).update(service_branch=None)


class Migration(migrations.Migration):

    dependencies = [
        ("userprofile", "0024_volunteers"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profile",
            name="service_branch",
            field=models.CharField(choices=[("ARMY", "US Army"), ("NAVY", "US Navy"), ("AIR_FORCE", "US Air Force"), ("MARINE CORPS", "US Marine Corps"), ("COAST_GUARD", "US Coast Guard"), ("SPACE_FORCE", "Space Force")], default=None, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name="veteranprofile",
            name="service_branch",
            field=models.CharField(choices=[("ARMY", "Army"), ("NAVY", "Navy"), ("AIR_FORCE", "Air Force"), ("MARINES", "Marines"), ("COAST_GUARD", "Coast Guard"), ("SPACE_FORCE", "Space Force")], default=None, max_length=200, null=True),
        ),
        # No reverse: None is what a missing branch should have been all along
        migrations.RunPython(clear_old_default, migrations.RunPython.noop),
    ]
