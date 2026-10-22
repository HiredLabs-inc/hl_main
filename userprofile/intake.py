"""Where new signups enter the pipeline: the Intake flow, starting at the step
gated by the veteran review permission (non-veterans skip it)."""
import logging

from django.db import transaction

from pipeline import services
from pipeline.models import Enrollment, Flow

from .guards import VETERAN_REVIEW_PERMISSION

INTAKE_SLUG = "intake"

logger = logging.getLogger(__name__)


def start_intake(user, is_veteran=True):
    """Enroll user in Intake unless they're already in any flow (onboarding can
    run more than once, BUG-003). Returns the new enrollment or None."""
    if Enrollment.objects.filter(person=user).exists():
        return None
    try:
        intake = Flow.objects.get(slug=INTAKE_SLUG)
    except Flow.DoesNotExist:
        # Never block a signup; staff can enroll them by hand
        logger.error("No Intake flow; user %s was not enrolled", user.pk)
        return None
    step = intake.first_step()
    if step is not None and not is_veteran and step.required_permission == VETERAN_REVIEW_PERMISSION:
        step = step.next_step() or step
    try:
        return services.enroll(user, intake, actor=user, step=step)
    except services.AlreadyEnrolled:
        return None


def awaiting_veteran_review(user):
    """The person's open Intake enrollment if it's on the veteran review step"""
    return (
        Enrollment.objects.filter(
            person=user,
            flow__slug=INTAKE_SLUG,
            ended_at__isnull=True,
            current_step__required_permission=VETERAN_REVIEW_PERMISSION,
        )
        .select_related("current_step__phase")
        .first()
    )


@transaction.atomic
def verify_and_advance(profile, actor):
    """Mark the veteran verified and move their Intake enrollment to the next step
    (Triage). Returns the enrollment, or None if they weren't awaiting review."""
    enrollment = awaiting_veteran_review(profile.user)
    next_step = enrollment.current_step.next_step() if enrollment else None
    if next_step is None:
        return None
    profile.veteran_verified = True
    profile.save(update_fields=["veteran_verified", "updated_at"])
    return services.move_to_step(enrollment, next_step, actor)
