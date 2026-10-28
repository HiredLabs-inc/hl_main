"""Move the seeded agents to Gemini on Vertex (docs/gcp-agents.md §4 M,
IDEA-008), price the tools for Google Search grounding, put the web_search
task on a faster model, and pace the funding prompt for Gemini.

Each change is only made to values that are still the seeded ones, so settings
edited on /agents/settings/ are kept. Ollama Cloud stays, so an agent can be
switched back.
"""
from importlib import import_module

from django.conf import settings
from django.db import migrations

seed_0002 = import_module("hlagents.migrations.0002_seed_agents")
seed_0007 = import_module("hlagents.migrations.0007_lead_quality")
seed_0009 = import_module("hlagents.migrations.0009_seed_ai_tasks")

AGENTS = list(seed_0007.PROMPTS)
OLLAMA_PROVIDER = "Ollama Cloud"
# Google bills $14 per 1,000 grounding queries on Gemini 3, after 5,000 free a
# month (2026-10-28). One search can send more than one query. Pages are
# fetched directly, at no charge.
RATES = {"web_search": "0.014", "read_page": "0"}
# In the comparison it was 35-65% faster than GEMINI_MODEL, with outreach leads as good
SEARCH_MODEL = "gemini-3.5-flash-lite"

# Gemini made one tool call per step, spent most steps on one funder, and at the
# step limit answered [] although it had read program pages (docs/gcp-agents.md §9 M)
PACING = """4. Work in parallel: in each step, make several tool calls at once, e.g. several searches, or reads of \
several programs' pages. You have a limited number of steps, so spend no more than two or three on any one funder, \
and move on if its page can't be read.
5. If you're told you're at the step limit, answer with every program whose own page you've read and that meets the \
criteria, with "" for anything its page didn't state. Return [] only if you haven't read any.

"""
STEP_3_END = "with no next cycle.\n\n"
OLD_FUNDING_PROMPT = seed_0007.FUNDING_PROMPT
FUNDING_PROMPT = OLD_FUNDING_PROMPT.replace(STEP_3_END, STEP_3_END + PACING, 1)


def _move(apps, from_provider, from_model, to_provider, to_model, old_rates, new_rates,
          old_search_model, new_search_model, old_prompt, new_prompt):
    ProviderConfig = apps.get_model("hlagents", "ProviderConfig")
    AgentConfig = apps.get_model("hlagents", "AgentConfig")
    AgentLimits = apps.get_model("hlagents", "AgentLimits")
    TaskConfig = apps.get_model("hlagents", "TaskConfig")
    TaskConfig.objects.filter(key="web_search", model=old_search_model).update(model=new_search_model)
    AgentConfig.objects.filter(name="Funding opportunities", system_prompt=old_prompt).update(system_prompt=new_prompt)
    source = ProviderConfig.objects.filter(name=from_provider).first()
    target = ProviderConfig.objects.filter(name=to_provider).first()
    if source and target:
        AgentConfig.objects.filter(name__in=AGENTS, provider=source, model=from_model).update(
            provider=target, model=to_model
        )
    for limits in AgentLimits.objects.filter(pk=1):
        if limits.tool_costs == old_rates:
            limits.tool_costs = new_rates
            limits.save(update_fields=["tool_costs"])


def move(apps, schema_editor):
    _move(
        apps, OLLAMA_PROVIDER, seed_0002.DEFAULT_MODEL, seed_0009.GEMINI_PROVIDER, settings.GEMINI_MODEL,
        seed_0007.RATES, RATES, settings.GEMINI_MODEL, SEARCH_MODEL, OLD_FUNDING_PROMPT, FUNDING_PROMPT,
    )


def move_back(apps, schema_editor):
    _move(
        apps, seed_0009.GEMINI_PROVIDER, settings.GEMINI_MODEL, OLLAMA_PROVIDER, seed_0002.DEFAULT_MODEL,
        RATES, seed_0007.RATES, SEARCH_MODEL, settings.GEMINI_MODEL, FUNDING_PROMPT, OLD_FUNDING_PROMPT,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("hlagents", "0012_web_search_task"),
    ]

    operations = [
        migrations.RunPython(move, move_back),
    ]
