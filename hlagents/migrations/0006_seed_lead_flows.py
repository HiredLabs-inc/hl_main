"""Seed the Funding and Outreach lead flows (docs/hlagents.md §3.6) and enroll
leads that are already approved: imported partners at Partner, the rest at
the first step.
"""
from django.db import migrations
from django.utils import timezone

# (slug, name, description, order, [(phase, [steps])])
FLOWS = [
    (
        "funding",
        "Funding",
        "Funding opportunities found by the agents, from research to the funder's decision.",
        100,
        [("Prospect", ["Found", "Researching"]), ("Application", ["Applying", "Submitted"]), ("Decision", ["Awarded", "Declined"])],
    ),
    (
        "outreach",
        "Outreach",
        "People at veteran-serving organizations who could refer veterans to the boot camps.",
        101,
        [("Prospect", ["Found"]), ("Outreach", ["Contacted", "Replied"]), ("Partner", ["Partner"])],
    ),
]
PARTNER_STEP = "Partner"


def seed(apps, schema_editor):
    Flow = apps.get_model("pipeline", "Flow")
    Phase = apps.get_model("pipeline", "Phase")
    Step = apps.get_model("pipeline", "Step")
    Enrollment = apps.get_model("pipeline", "Enrollment")
    Activity = apps.get_model("pipeline", "Activity")
    Lead = apps.get_model("hlagents", "Lead")

    for slug, name, description, order, phases in FLOWS:
        flow, created = Flow.objects.get_or_create(
            slug=slug, defaults={"name": name, "description": description, "order": order, "subject": "lead"}
        )
        if not created:
            continue
        for phase_order, (title, steps) in enumerate(phases):
            phase = Phase.objects.create(flow=flow, title=title, order=phase_order)
            for step_order, step in enumerate(steps):
                Step.objects.create(phase=phase, title=step, order=step_order)

    now = timezone.now()
    for lead in Lead.objects.filter(review_status="approved"):
        flow = Flow.objects.get(slug=lead.kind)
        steps = Step.objects.filter(phase__flow=flow).order_by("phase__order", "order")
        step = steps.get(title=PARTNER_STEP) if lead.source == "import" else steps.first()
        if Enrollment.objects.filter(lead=lead, flow=flow, ended_at__isnull=True).exists():
            continue
        enrollment = Enrollment.objects.create(lead=lead, flow=flow, current_step=step, step_entered_at=now)
        Activity.objects.create(lead=lead, enrollment=enrollment, kind="enrolled", to_value=step.title)


def unseed(apps, schema_editor):
    Flow = apps.get_model("pipeline", "Flow")
    apps.get_model("pipeline", "Enrollment").objects.filter(flow__slug__in=[f[0] for f in FLOWS]).delete()
    Flow.objects.filter(slug__in=[f[0] for f in FLOWS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("hlagents", "0005_agent_admins_and_prompts"),
        ("pipeline", "0005_lead_enrollments"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
