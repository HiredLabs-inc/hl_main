"""BUG-037: Completed only from a final step, and a Dropped status. Adds the
final steps: Graduated for Boot Camp, and a placeholder Service Complete for
Resume & Job Search (rename it once the flow's outcome is defined). Intake ends
through triage and Nurture has no end, so neither gets one. Existing
enrollments are left as they are.
"""
from django.db import migrations, models

# flow slug -> (phase title, step title, step description)
FINAL_STEPS = {
    "boot-camp": ("Graduation", "Graduated", "Finished the boot camp course. Complete the enrollment from here."),
    "resume-job-search": (
        "Finish",
        "Service Complete",
        "Placeholder until the flow's outcome is defined. Complete the enrollment from here.",
    ),
}


def add_final_steps(apps, schema_editor=None):
    Flow = apps.get_model("pipeline", "Flow")
    Phase = apps.get_model("pipeline", "Phase")
    Step = apps.get_model("pipeline", "Step")
    for slug, (phase_title, step_title, description) in FINAL_STEPS.items():
        flow = Flow.objects.filter(slug=slug).first()
        if flow is None:
            continue
        step = Step.objects.filter(phase__flow=flow, title=step_title).first()
        if step is None:
            phase = Phase.objects.filter(flow=flow, title=phase_title).first()
            if phase is None:
                last = Phase.objects.filter(flow=flow).order_by("-order").first()
                phase = Phase.objects.create(flow=flow, title=phase_title, order=last.order + 1 if last else 0)
            step = Step.objects.create(phase=phase, title=step_title, description=description, order=phase.steps.count())
        Step.objects.filter(pk=step.pk).update(completes_flow=True)


def remove_final_steps(apps, schema_editor=None):
    Step = apps.get_model("pipeline", "Step")
    Phase = apps.get_model("pipeline", "Phase")
    for slug, (phase_title, step_title, _) in FINAL_STEPS.items():
        # PROTECT stops this if anyone has been moved onto the step
        Step.objects.filter(phase__flow__slug=slug, title=step_title).delete()
        Phase.objects.filter(flow__slug=slug, title=phase_title, steps__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pipeline", "0003_activity_session_change"),
    ]

    operations = [
        migrations.AddField(
            model_name="step",
            name="completes_flow",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="enrollment",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("paused", "Paused"),
                    ("rejected", "Rejected"),
                    ("no_show", "No show"),
                    ("completed", "Completed"),
                    ("withdrawn", "Withdrawn"),
                    ("dropped", "Dropped"),
                ],
                default="active",
                max_length=20,
            ),
        ),
        migrations.RunPython(add_final_steps, remove_final_steps),
    ]
