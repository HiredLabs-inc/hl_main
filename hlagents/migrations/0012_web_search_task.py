"""Seed the web_search task (docs/gcp-agents.md §3.2, IDEA-008 S): the Gemini
call with Google Search grounding behind the agents' web_search tool, on the
Gemini provider 0009 seeded.
"""
from importlib import import_module

from django.conf import settings
from django.db import migrations, models

seed_0009 = import_module("hlagents.migrations.0009_seed_ai_tasks")

KEY = "web_search"
# google_search turns on grounding; a low temperature keeps the summaries close to the sources
OPTIONS = {**seed_0009.OPTIONS, "temperature": 0.2, "google_search": True}

INSTRUCTIONS = """You search the web with Google for an assistant that's researching. The message is its search \\
query.

Search for the query, then say what each relevant source says about it, one short paragraph per source: who \\
runs it, what it offers or asks for, amounts, dates and eligibility. Stick to what the sources say, and don't \\
answer from memory. If nothing relevant comes up, say so."""


def seed(apps, schema_editor):
    ProviderConfig = apps.get_model("hlagents", "ProviderConfig")
    TaskConfig = apps.get_model("hlagents", "TaskConfig")
    provider, _ = ProviderConfig.objects.get_or_create(name=seed_0009.GEMINI_PROVIDER, defaults={"kind": "gemini"})
    TaskConfig.objects.get_or_create(
        key=KEY,
        defaults={"provider": provider, "model": settings.GEMINI_MODEL, "instructions": INSTRUCTIONS, "options": OPTIONS},
    )


def unseed(apps, schema_editor):
    apps.get_model("hlagents", "TaskConfig").objects.filter(key=KEY).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("hlagents", "0011_run_stop"),
    ]

    operations = [
        migrations.AlterField(
            model_name="taskconfig",
            name="key",
            field=models.CharField(
                choices=[
                    ("resume_overview", "Resume overview"),
                    ("resume_bullets", "Resume bullet points"),
                    ("bullet_rewrite", "Bullet rewrite for a job"),
                    ("job_keywords", "Job description keywords"),
                    ("web_search", "Web search for agents"),
                ],
                max_length=50,
                unique=True,
            ),
        ),
        migrations.RunPython(seed, unseed),
    ]
