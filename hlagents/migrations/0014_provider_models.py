"""Lists the models anyone who runs agents can pick on /agents/, per provider.

Each provider starts with the models its agents and tasks use now. Ollama Cloud
also gets the prototype's model, which its agents used before 0013.
"""
from importlib import import_module

from django.db import migrations, models

seed_0002 = import_module("hlagents.migrations.0002_seed_agents")
seed_0013 = import_module("hlagents.migrations.0013_agents_on_gemini")


def seed_models(apps, schema_editor):
    ProviderConfig = apps.get_model("hlagents", "ProviderConfig")
    for provider in ProviderConfig.objects.all():
        used = list(provider.agents.values_list("model", flat=True)) + list(provider.tasks.values_list("model", flat=True))
        if provider.name == seed_0013.OLLAMA_PROVIDER:
            used.append(seed_0002.DEFAULT_MODEL)
        provider.models = list(dict.fromkeys(m for m in used if m))
        provider.save(update_fields=["models"])


class Migration(migrations.Migration):
    dependencies = [
        ("hlagents", "0013_agents_on_gemini"),
    ]

    operations = [
        migrations.AddField(
            model_name="providerconfig",
            name="models",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(seed_models, migrations.RunPython.noop),
    ]
