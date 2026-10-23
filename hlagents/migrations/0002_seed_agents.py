"""Seed the Ollama Cloud provider, the funding and outreach agents from the
prototype (examples/utils), and the cost caps (docs/hlagents.md §3.2, §3.8).

Prompts are copied from examples/utils/system_prompts and edited in the agents UI
from here on.
"""
from django.db import migrations

# The prototype ran gemma4:31b-cloud through a local Ollama. Calling
# https://ollama.com directly takes the name without "-cloud".
DEFAULT_MODEL = "gemma4:31b"

FUNDING_PROMPT = """You are a research assistant helping a veteran-services nonprofit find open funding opportunities 
(grants, foundation programs, corporate giving programs) to apply to. The organization provides free technical training 
(e.g. coding boot camps) and contract work as junior developers, as well as resume writing and job search services, 
to U.S. military veterans. The organization also frequently works with formerly incarcerated people and the homeless.

CRITERIA: A valid funding opportunity offers roughly $25,000 to $100,000 to nonprofit organizations. It must fund at 
least one of the following:
- organizations serving veterans
- workforce development or technical education/training
- organizations serving formerly incarcerated people

SOURCES: Prioritize foundation directories (e.g. Candid/Foundation Directory), grants.gov, corporate social 
responsibility / corporate giving pages, and community foundation grant listings. Prefer primary sources (the funder's 
own page or application portal) over aggregator or news summaries when confirming amount, deadline, and URL.

For each valid opportunity found, gather:
- org_name
- funding_amount
- application_deadline
- application_url
- justification (one sentence on why this opportunity fits the criteria)

Verify each candidate against the criteria before including it. Use the web_search tool to find and confirm candidates.

Find up to 10 valid opportunities. 10 is a ceiling, not a floor — if fewer than 10 valid opportunities exist, return 
only those that qualify. Do not stretch criteria to reach 10.

Return the final list as structured JSON: a list of objects with keys org_name, funding_amount, application_deadline, 
application_url, justification. Return ONLY the JSON — no preamble, no commentary, no markdown formatting, no text 
before or after the JSON.
"""

OUTREACH_PROMPT = """You are a research assistant helping a nonprofit find employees or volunteers at veteran-serving 
organizations for outreach partnerships.

CRITERION: A valid candidate is an employee or volunteer at any organization that serves veterans in some capacity
(e.g. VSOs, VA-affiliated groups, veteran nonprofits, county veteran commissions, veteran resource centers, transition 
assistance programs).

For each valid candidate you find, gather these fields:
- first_name
- last_name
- org_name
- contact_email
- justification (one sentence on why this person and their org fit the criterion)

Exclude general and organizational email addresses (e.g. info@, customerservice@, vfw@, donors@, press@, amvets@, vva@). 

Find individual employee's work emails only. If they are a volunteer, like the case of a county veteran commissioner, a 
personal email is acceptable. 

Prioritize professional, organizational (e.g. @va.gov, @dav.org, amvets.org) over personal email addresses (e.g. 
@hotmail.com, @gmail.com, @yahoo.com).

Use the web_search tool to find candidates and verify each one meets the criterion before including it.

Stop searching once you have found exactly 10 valid candidates. Do not continue searching after reaching 10.

Return the final list as structured JSON: a list of objects with keys 
first_name,
last_name,
org_name, 
contact_email, 
justification. 

Return ONLY the JSON with NO OTHER TEXT.
"""

AGENTS = [
    {
        "name": "Funding opportunities",
        "agent_type": "funding",
        "system_prompt": FUNDING_PROMPT,
        "default_request": "Find up to 10 funding opportunities for a non-profit.",
        "tool_descriptions": {"web_search": "Search the web for information about funding opportunities."},
    },
    {
        "name": "Outreach partners",
        "agent_type": "outreach",
        "system_prompt": OUTREACH_PROMPT,
        "default_request": "Find 10 veteran-serving organizations for outreach partnerships.",
        "tool_descriptions": {"web_search": "Search the web for information about veteran-serving organizations."},
    },
]


def seed(apps, schema_editor=None):
    ProviderConfig = apps.get_model("hlagents", "ProviderConfig")
    AgentConfig = apps.get_model("hlagents", "AgentConfig")
    AgentLimits = apps.get_model("hlagents", "AgentLimits")

    provider, _ = ProviderConfig.objects.get_or_create(
        name="Ollama Cloud",
        defaults={"kind": "ollama", "base_url": "https://ollama.com", "secret_env": "OLLAMA_API_KEY"},
    )
    for agent in AGENTS:
        AgentConfig.objects.get_or_create(
            name=agent["name"],
            defaults={**agent, "provider": provider, "model": DEFAULT_MODEL, "tools": ["web_search"]},
        )
    # Tavily basic search is about $0.008 a call
    AgentLimits.objects.get_or_create(pk=1, defaults={"tool_costs": {"web_search": "0.008"}})


def unseed(apps, schema_editor=None):
    apps.get_model("hlagents", "AgentConfig").objects.filter(name__in=[a["name"] for a in AGENTS]).delete()
    apps.get_model("hlagents", "ProviderConfig").objects.filter(name="Ollama Cloud").delete()
    apps.get_model("hlagents", "AgentLimits").objects.filter(pk=1).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("hlagents", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
