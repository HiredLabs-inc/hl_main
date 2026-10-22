"""Seed the four flows from the cold_apply phases and steps, and give each
existing participant an enrollment on the copied step (design doc §8 Step 3).

Old phases are matched to flows by title. An unknown phase stops the migration
rather than guessing where its participants belong.
"""
import re

from django.db import migrations
from django.utils import timezone

FLOWS = [
    ("intake", "Intake", "New applicants: verify veteran status, then decide which flows they join."),
    ("resume-job-search", "Resume & Job Search", "Tailored resumes and job applications."),
    ("boot-camp", "Boot Camp", "Boot camp on-boarding and wait list."),
    ("nurture", "Nurture", "Keeping in touch with alumni and past participants. Steps to be defined (IDEA-006)."),
]
DNC_PHASE = "Do Not Contact"
VERIFY_STEP = "Verify Veteran Status"
VETERAN_REVIEW_PERMISSION = "userprofile.review_veteran_status"
# Old steps that become an enrollment status instead of a step. People on them
# stay on the copied step before it in the same phase.
STATUS_STEPS = {"No Show": "no_show", "Send Rejection Message": "rejected"}
RENAMED_STEPS = {
    ("Nurture", "Monthly Newsletter"): (
        "Nurture",
        "Placeholder until the Nurture flow is defined (IDEA-006).",
    ),
}
MIGRATED_NOTE = "Moved from the old Cold Apply steps"
INTERACTION_KINDS = {"EMAIL": "email", "PHONE": "phone", "IN_PERSON": "in_person"}


def flow_slug_for(phase_title):
    if phase_title == "Applicants":
        return "intake"
    if re.fullmatch(r"Phase \d+", phase_title):
        return "resume-job-search"
    if phase_title.startswith("Boot Camp"):
        return "boot-camp"
    if phase_title == "Nurture":
        return "nurture"
    return None


def seed_flows(apps, schema_editor=None):
    OldPhase = apps.get_model("cold_apply", "Phase")
    Participant = apps.get_model("cold_apply", "Participant")
    Interaction = apps.get_model("cold_apply", "Interaction")
    Profile = apps.get_model("userprofile", "Profile")
    Flow = apps.get_model("pipeline", "Flow")
    Phase = apps.get_model("pipeline", "Phase")
    Step = apps.get_model("pipeline", "Step")
    Enrollment = apps.get_model("pipeline", "Enrollment")
    Activity = apps.get_model("pipeline", "Activity")

    old_phases = list(OldPhase.objects.order_by("order", "id"))
    unknown = [p.title for p in old_phases if p.title != DNC_PHASE and flow_slug_for(p.title) is None]
    if unknown:
        raise RuntimeError(
            f"Don't know which flow these cold_apply phases belong to: {', '.join(unknown)}. "
            "Add them to flow_slug_for in pipeline/migrations/0002_seed_flows.py."
        )

    flows = {
        slug: Flow.objects.create(slug=slug, name=name, description=description, order=i)
        for i, (slug, name, description) in enumerate(FLOWS)
    }

    # old step id -> (new step, status); status is "active" unless the old step became a status
    step_map = {}
    phase_counts = dict.fromkeys(flows, 0)
    for old_phase in old_phases:
        slug = flow_slug_for(old_phase.title)
        if slug is None:
            continue
        phase = Phase.objects.create(
            flow=flows[slug],
            title=old_phase.title,
            start=old_phase.start,
            end=old_phase.end,
            result=old_phase.result,
            order=phase_counts[slug],
        )
        phase_counts[slug] += 1
        previous = None
        status_steps = []
        for old_step in old_phase.step_set.order_by("order", "id"):
            if old_step.title in STATUS_STEPS:
                status_steps.append((old_step, previous))
                continue
            title, description = RENAMED_STEPS.get(
                (old_phase.title, old_step.title), (old_step.title, old_step.description)
            )
            previous = Step.objects.create(
                phase=phase,
                title=title,
                description=description,
                owner=old_step.owner,
                order=phase.steps.count(),
                required_permission=VETERAN_REVIEW_PERMISSION if old_step.title == VERIFY_STEP else "",
            )
            step_map[old_step.pk] = (previous, "active")
        for old_step, previous in status_steps:
            step_map[old_step.pk] = (previous or phase.steps.order_by("order").first(), STATUS_STEPS[old_step.title])

    intake = flows["intake"]
    applicants = intake.phases.first() or Phase.objects.create(flow=intake, title="Applicants")
    if not Step.objects.filter(phase__flow=intake, title=VERIFY_STEP).exists():
        Step.objects.create(
            phase=applicants,
            title=VERIFY_STEP,
            order=applicants.steps.count(),
            required_permission=VETERAN_REVIEW_PERMISSION,
        )
    triage = Step.objects.create(
        phase=applicants,
        title="Triage",
        description="Decide which flows this person joins.",
        order=applicants.steps.count(),
    )
    # Fresh databases have no old phases; give every flow a step so people can be enrolled
    for slug, flow in flows.items():
        if not Step.objects.filter(phase__flow=flow).exists():
            phase = flow.phases.first() or Phase.objects.create(flow=flow, title=flow.name)
            Step.objects.create(phase=phase, title=flow.name, order=0)

    now = timezone.now()
    for participant in Participant.objects.select_related("current_step__phase").order_by("id"):
        old_step = participant.current_step
        if old_step is not None and old_step.phase.title == DNC_PHASE:
            Profile.objects.update_or_create(user_id=participant.user_id, defaults={"dnc": True})
            Activity.objects.create(
                person_id=participant.user_id,
                kind="note",
                text=f"Marked do not contact (was on {DNC_PHASE}: {old_step.title})",
            )
            continue
        step, status = step_map.get(old_step.pk, (None, "")) if old_step else (triage, "active")
        if step is None:
            raise RuntimeError(f"No step to put participant {participant.pk} on (was on {old_step.title}).")
        enrollment = Enrollment.objects.create(
            person_id=participant.user_id,
            flow=step.phase.flow,
            current_step=step,
            status=status,
            step_entered_at=participant.updated_at,
        )
        Enrollment.objects.filter(pk=enrollment.pk).update(created_at=participant.created_at)
        Activity.objects.create(
            person_id=participant.user_id,
            enrollment=enrollment,
            kind="enrolled",
            text=MIGRATED_NOTE,
            to_value=step.title,
        )
        if status != "active":
            Activity.objects.create(
                person_id=participant.user_id,
                enrollment=enrollment,
                kind="status_change",
                text=f"Was on the old step {old_step.title}",
                from_value="Active",
                to_value=dict(Enrollment._meta.get_field("status").choices)[status],
            )

    for interaction in Interaction.objects.select_related("participant").order_by("id"):
        activity = Activity.objects.create(
            person_id=interaction.participant.user_id,
            kind=INTERACTION_KINDS.get(interaction.interaction_type, "note"),
            text=interaction.notes or "",
            actor_id=interaction.user_id,
        )
        Activity.objects.filter(pk=activity.pk).update(created_at=interaction.created_at or now)


def unseed_flows(apps, schema_editor=None):
    # Profile.dnc is left as it is: one profile was already marked before this migration
    for model in ("Activity", "Enrollment", "Step", "Phase", "Flow"):
        apps.get_model("pipeline", model).objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pipeline", "0001_initial"),
        ("cold_apply", "0003_alter_job_status_reason"),
        ("userprofile", "0022_review_veteran_status"),
    ]

    operations = [
        migrations.RunPython(seed_flows, unseed_flows),
    ]
