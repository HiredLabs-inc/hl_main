from django.conf import settings
from django.db import migrations


def set_site(apps, schema_editor):
    # 0003 defined this but never ran it (empty operations), so new databases
    # kept Django's default "example.com", which allauth puts in emails.
    Site = apps.get_model("sites", "Site")
    if Site.objects.exclude(id=settings.SITE_ID).filter(domain="hiredlabs.org").exists():
        return  # domain is unique; another row already owns it (legacy databases)
    Site.objects.update_or_create(
        id=settings.SITE_ID,
        defaults={"domain": "hiredlabs.org", "name": "hiredlabs.org"},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("userprofile", "0014_profile_bootcamp"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [migrations.RunPython(set_site, migrations.RunPython.noop)]
