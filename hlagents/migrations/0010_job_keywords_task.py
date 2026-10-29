"""Seed the job_keywords task (docs/designs/completed/ai-tasks.md §3.6, IDEA-007 K) on the
Gemini provider 0009 seeded, with the model the resume tasks were seeded with.
"""
from importlib import import_module

from django.conf import settings
from django.db import migrations, models

seed_0009 = import_module("hlagents.migrations.0009_seed_ai_tasks")

KEY = "job_keywords"
# Low temperature, so refreshing a job's keywords mostly gives the same ones
OPTIONS = {**seed_0009.OPTIONS, "temperature": 0.2}

INSTRUCTIONS = """You pick out the keywords in a job description that a resume should use, so a U.S. military \\
veteran can tailor their resume to the job.

Keywords are the skills, tools, technologies, certifications, qualifications and duties the job asks for, e.g. \\
"Python", "project management", "valid security clearance". Leave out everything else: the company's description, \\
benefits, pay, location, schedule, equal opportunity and legal text, and generic words like "experience", \\
"candidate" or "team player".

Rules:
- Copy each phrase word for word from the description, with its words in the same order. Never reorder, \\
abbreviate, expand or invent words. Keep spellings like "C++", "Node.js" and "CI/CD" as they appear.
- unigrams are single words, bigrams are exactly two words, and trigrams are exactly three words.
- Give up to 20 of each, most important first. Don't repeat a phrase within a list.

Reply with only a JSON object, e.g. {"unigrams": ["Python", "SQL"], "bigrams": ["data analysis"], \\
"trigrams": ["valid security clearance"]}."""


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
        ("hlagents", "0009_seed_ai_tasks"),
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
                ],
                max_length=50,
                unique=True,
            ),
        ),
        migrations.RunPython(seed, unseed),
    ]
