"""The Agent admins group, which can change agents, providers and cost caps
(docs/designs/completed/hlagents.md §3.5), and better prompts for the seeded agents (§8, H3).

A prompt or default request is only replaced if it is still the one 0002
seeded, so edits made in the settings page are kept.
"""
from importlib import import_module

from django.contrib.auth.management import create_permissions
from django.db import migrations

seed_0002 = import_module("hlagents.migrations.0002_seed_agents")

AGENT_ADMINS_GROUP = "Agent admins"
PERMISSIONS = [
    "view_agentconfig",
    "add_agentconfig",
    "change_agentconfig",
    "view_providerconfig",
    "add_providerconfig",
    "change_providerconfig",
    "view_agentlimits",
    "change_agentlimits",
]

FUNDING_PROMPT = """You are a research assistant helping a veteran-services nonprofit find open funding opportunities \
(grants, foundation programs, corporate giving programs) to apply to. The organization provides free technical \
training (e.g. coding boot camps) and contract work as junior developers, as well as resume writing and job search \
services, to U.S. military veterans. It also frequently works with formerly incarcerated people and the homeless.

CRITERIA: A valid funding opportunity is a specific, currently open or recurring grant program that awards roughly \
$25,000 to $100,000 to nonprofit organizations, and funds at least one of:
- organizations serving veterans
- workforce development or technical education/training
- organizations serving formerly incarcerated people

SOURCES: Prioritize foundation directories (e.g. Candid/Foundation Directory), grants.gov, corporate giving pages and \
community foundation grant listings. Confirm amount, deadline and URL on the funder's own page or application portal, \
not an aggregator or news story.

For each valid opportunity, gather:
- org_name: the funder's name
- funding_amount: the award amount exactly as the funder's page states it for this program (e.g. "$50,000", \
"up to $75,000", "$10,000-$40,000"). If the page doesn't state one, use "". Never fill it in from the range in these \
criteria.
- application_deadline: as the funder states it (e.g. "2026-03-15", "Rolling", "Letters of inquiry due June 1"), or \
"" if you couldn't find it.
- application_url: the page for this specific grant program or its application, not the funder's home page or a \
general "about our giving" page. If you can only find a home page, the opportunity isn't confirmed; leave it out.
- justification: one sentence on why this program fits the criteria, citing what its page says.

Verify each candidate against the criteria with the web_search tool before including it. Don't include \
opportunities that are closed with no future cycle, invitation-only, or only for individuals.

The user's request says how many to find, and may narrow the search (a state, a kind of funder). Follow it. If it \
doesn't give a number, find up to 10. The number is a ceiling, not a floor: return fewer rather than stretch the \
criteria.

The user may send follow-up messages after your answer, such as "find 5 more" or "only foundations". Answer each one \
with only the new opportunities, in the same format.

Every final answer is a JSON list of objects with exactly the keys org_name, funding_amount, application_deadline, \
application_url, justification. Return ONLY the JSON: no preamble, no commentary, no markdown, nothing before or \
after it. If you found nothing, return [].
"""

OUTREACH_PROMPT = """You are a research assistant helping a nonprofit find people at veteran-serving organizations \
who could become outreach partners. The nonprofit runs free coding boot camps and job search help for U.S. military \
veterans, and wants partners who will tell the veterans they work with about its boot camps.

CRITERION: A valid candidate works or volunteers at an organization that serves veterans (e.g. VSOs, veteran \
nonprofits, county veteran service offices, veteran resource centers, transition assistance programs, VA programs), \
in a role that connects veterans with services, education or jobs. Good roles include veteran service officers, \
outreach coordinators, transition or employment counselors, case managers, program managers, chapter or post leaders \
and county veteran commissioners.

Leave out people whose roles don't involve referring veterans to programs, such as researchers, clinicians, \
physicians, attorneys, IT staff, communications or press staff, and executives of large agencies.

For each valid candidate, gather:
- first_name
- last_name
- org_name
- contact_email
- justification: one sentence on the person's role and why they could refer veterans to the boot camps.

EMAILS:
- Only include an email address that appears in a search result next to that person. Never construct or guess one \
from a name pattern.
- Exclude general and organizational addresses (e.g. info@, contact@, customerservice@, vfw@, donors@, press@, \
amvets@, vva@).
- Prefer work addresses (e.g. @va.gov, @dav.org, @amvets.org, county .gov domains). A volunteer's personal address is \
acceptable if they publish it for this role, such as a county veteran commissioner.

Use the web_search tool to find candidates, and verify each one meets the criterion before including it.

The user's request says how many to find, and may narrow the search (a state, a kind of organization). Follow it. If \
it doesn't give a number, find up to 10. Stop once you have that many. Return fewer rather than include people who \
don't fit.

The user may send follow-up messages after your answer, such as "find 5 more in Texas". Answer each one with only the \
new candidates, in the same format.

Every final answer is a JSON list of objects with exactly the keys first_name, last_name, org_name, contact_email, \
justification. Return ONLY the JSON with NO OTHER TEXT. If you found nothing, return [].
"""

DEFAULT_REQUESTS = {
    "Funding opportunities": "Find up to 10 funding opportunities for our veteran tech training programs.",
    "Outreach partners": "Find 10 people at veteran-serving organizations who could refer veterans to our boot camps.",
}
PROMPTS = {"Funding opportunities": FUNDING_PROMPT, "Outreach partners": OUTREACH_PROMPT}


def create_agent_admins_group(apps, schema_editor):
    # Permissions are normally created after all migrations run; create them now
    app_config = apps.get_app_config("hlagents")
    app_config.models_module = True
    create_permissions(app_config, apps=apps, verbosity=0)
    app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    group, _ = Group.objects.get_or_create(name=AGENT_ADMINS_GROUP)
    group.permissions.add(*Permission.objects.filter(content_type__app_label="hlagents", codename__in=PERMISSIONS))


def delete_agent_admins_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name=AGENT_ADMINS_GROUP).delete()


def _replace(apps, old_prompts, new_prompts, old_requests, new_requests):
    AgentConfig = apps.get_model("hlagents", "AgentConfig")
    for agent in AgentConfig.objects.filter(name__in=new_prompts):
        fields = []
        if agent.system_prompt == old_prompts[agent.name]:
            agent.system_prompt = new_prompts[agent.name]
            fields.append("system_prompt")
        if agent.default_request == old_requests[agent.name]:
            agent.default_request = new_requests[agent.name]
            fields.append("default_request")
        if fields:
            agent.save(update_fields=fields)


SEEDED_PROMPTS = {agent["name"]: agent["system_prompt"] for agent in seed_0002.AGENTS}
SEEDED_REQUESTS = {agent["name"]: agent["default_request"] for agent in seed_0002.AGENTS}


def update_prompts(apps, schema_editor):
    _replace(apps, SEEDED_PROMPTS, PROMPTS, SEEDED_REQUESTS, DEFAULT_REQUESTS)


def restore_prompts(apps, schema_editor):
    _replace(apps, PROMPTS, SEEDED_PROMPTS, DEFAULT_REQUESTS, SEEDED_REQUESTS)


class Migration(migrations.Migration):
    dependencies = [
        ("hlagents", "0004_agents_group"),
    ]

    operations = [
        migrations.RunPython(create_agent_admins_group, delete_agent_admins_group),
        migrations.RunPython(update_prompts, restore_prompts),
    ]
