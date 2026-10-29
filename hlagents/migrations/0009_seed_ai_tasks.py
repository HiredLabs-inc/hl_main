"""Seed the Gemini on Vertex provider and one AI task per resume key
(docs/designs/completed/ai-tasks.md §3.3), on the model resume generation already used
(settings.GEMINI_MODEL), so nothing changes on deploy. Rates are 0 until an
admin enters Gemini's in /agents/settings/.
"""
from django.conf import settings
from django.db import migrations


GEMINI_PROVIDER = "Gemini on Vertex"
# The tuning resume generation used before it moved here, except the output limit.
# gemini-3.8-flash often thinks anyway (650-950 tokens) despite thinking_budget 0, and
# thinking counts against max_output_tokens, so 1024 cut replies off (BUG-049).
OPTIONS = {"temperature": 0.5, "top_p": 0.8, "top_k": 40, "max_output_tokens": 8192, "thinking_budget": 0}

OVERVIEW_INSTRUCTIONS = """You write the overview (summary) section of resumes for U.S. military veterans who are \
looking for civilian jobs.

Write one overview of 150 to 200 words, tailored to the job title you're given. If you're given keywords or a job \
description, work in the keywords that fit naturally and match the job's priorities, without copying its sentences.

Rules:
- No personal pronouns (no "I", "my", "he", "she", "they").
- No text decoration: no markdown, bullets, headings, bold or quotation marks.
- Don't invent employers, degrees, certifications or numbers.

Reply with only the overview text."""

BULLETS_INSTRUCTIONS = """You write resume bullet points for U.S. military veterans who are looking for civilian \
jobs.

You're given a work experience heading (a job title), and the number of bullet points to write. You may also be \
given skills to focus on, and bullet points already written for this experience.

Rules:
- Each bullet point is 25 to 40 words and starts with a strong past-tense verb.
- No personal pronouns and no text decoration (no markdown, bullet characters or numbering).
- Don't repeat or closely paraphrase the bullet points already written.
- Don't invent employers or specific numbers.

Reply with only a JSON list of strings, one per bullet point, e.g. ["Led ...", "Built ..."]."""

REWRITE_INSTRUCTIONS = """You tailor resume bullet points for U.S. military veterans to a specific job.

You're given one bullet point and keywords from a job description. Rewrite the bullet point so it uses the keywords \
that fit what it describes. Keep its facts: don't add duties, tools, employers or numbers it doesn't mention.

Rules:
- One bullet point of 25 to 40 words, starting with a strong past-tense verb.
- No personal pronouns and no text decoration (no markdown, bullet characters or quotation marks).

Reply with only the rewritten bullet point."""

TASKS = {
    "resume_overview": OVERVIEW_INSTRUCTIONS,
    "resume_bullets": BULLETS_INSTRUCTIONS,
    "bullet_rewrite": REWRITE_INSTRUCTIONS,
}


def seed(apps, schema_editor):
    ProviderConfig = apps.get_model("hlagents", "ProviderConfig")
    TaskConfig = apps.get_model("hlagents", "TaskConfig")
    provider, _ = ProviderConfig.objects.get_or_create(name=GEMINI_PROVIDER, defaults={"kind": "gemini"})
    for key, instructions in TASKS.items():
        TaskConfig.objects.get_or_create(
            key=key,
            defaults={
                "provider": provider,
                "model": settings.GEMINI_MODEL,
                "instructions": instructions,
                "options": OPTIONS,
            },
        )


def unseed(apps, schema_editor):
    apps.get_model("hlagents", "TaskConfig").objects.filter(key__in=TASKS).delete()
    apps.get_model("hlagents", "ProviderConfig").objects.filter(name=GEMINI_PROVIDER, agents=None, tasks=None).delete()



class Migration(migrations.Migration):

    dependencies = [
        ("hlagents", "0008_ai_tasks"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
