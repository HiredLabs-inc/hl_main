"""Boot Camp enrollments and the sessions (cohorts) they're placed in. A Boot
Camp enrollment without a session is on the waitlist."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from pipeline import services
from pipeline.models import Activity, Enrollment, Step

from .models import BootCampSeat, BootCampSession

FLOW_SLUG = "boot-camp"
WAITLIST = "Waitlist"
# Where a session moves people, unless they're already at or past it (Jeff, 2026-10-20)
CONFIRMATION_STEP = "Send Enrollment Confirmation"


def is_boot_camp(enrollment: Enrollment) -> bool:
    return enrollment.flow.slug == FLOW_SLUG


def add_sessions(enrollments):
    """Set session (None means waitlist), session_choices (upcoming sessions)
    and past_sessions (latest first, so a past cohort can be recorded) on each
    Boot Camp enrollment, in two queries."""
    enrollments = [enrollment for enrollment in enrollments if is_boot_camp(enrollment)]
    if not enrollments:
        return
    seats = BootCampSeat.objects.filter(enrollment__in=enrollments).select_related("session")
    sessions = {seat.enrollment_id: seat.session for seat in seats}
    today = timezone.localdate()
    every = list(BootCampSession.objects.all())
    upcoming = [session for session in every if session.start_date >= today]
    past = [session for session in reversed(every) if session.start_date < today]
    for enrollment in enrollments:
        enrollment.session = sessions.get(enrollment.pk)
        enrollment.session_choices = upcoming
        enrollment.past_sessions = past


def has_started(enrollment: Enrollment) -> bool:
    """They have a seat in a session that has started. Uses the session from
    add_sessions when it has been set."""
    if hasattr(enrollment, "session"):
        session = enrollment.session
    else:
        seat = BootCampSeat.objects.filter(enrollment=enrollment).select_related("session").first()
        session = seat.session if seat else None
    return session is not None and session.start_date <= timezone.localdate()


def status_rule(enrollment: Enrollment, refusals):
    """pipeline.services STATUS_RULES entry (BUG-037): once their session has
    started they can be dropped or (from Graduated) completed, not withdrawn.
    Before that they can only be withdrawn, or put back on the waitlist."""
    if not is_boot_camp(enrollment):
        return
    completed, withdrawn, dropped = Enrollment.Status.COMPLETED, Enrollment.Status.WITHDRAWN, Enrollment.Status.DROPPED
    if has_started(enrollment):
        refusals[withdrawn] = "Their session has started; drop them instead."
        refusals[dropped] = ""
    else:
        refusals[dropped] = "Only students whose session has started can be dropped; withdraw them instead."
        refusals[completed] = refusals[completed] or "Give them a session that has started first."


def _confirmation_step(enrollment):
    """The step a new session moves this enrollment to, or None to leave it where
    it is: when the flow has no confirmation step, or they're already at or after
    it in its phase (calendar invite, active student...). People elsewhere, such
    as the Wait List phase, move."""
    target = Step.objects.filter(phase__flow=enrollment.flow, title=CONFIRMATION_STEP).first()
    current = enrollment.current_step
    if target is None or (current.phase_id == target.phase_id and (current.order, current.pk) >= (target.order, target.pk)):
        return None
    return target


@transaction.atomic
def assign_session(enrollment: Enrollment, session, actor):
    """Give a Boot Camp enrollment a seat in session, or put it back on the
    waitlist when session is None. Recorded on the person's timeline. A seat
    also moves an open enrollment on to Send Enrollment Confirmation (see
    _confirmation_step); returns that step if they moved, otherwise None. Ended
    enrollments can be given a session too, to record which cohort they were in."""
    enrollment = Enrollment.objects.select_for_update(of=("self",)).select_related("flow").get(pk=enrollment.pk)
    if not is_boot_camp(enrollment):
        raise ValidationError("Only Boot Camp enrollments have sessions.")
    seat = BootCampSeat.objects.filter(enrollment=enrollment).select_related("session").first()
    old = seat.session if seat else None
    if old == session:
        return None
    if session is None:
        seat.delete()
    elif seat is None:
        BootCampSeat.objects.create(enrollment=enrollment, session=session)
    else:
        seat.session = session
        seat.save(update_fields=["session"])
    Activity.objects.create(
        person=enrollment.person,
        enrollment=enrollment,
        kind=Activity.Kind.SESSION_CHANGE,
        from_value=old.label if old else WAITLIST,
        to_value=session.label if session else WAITLIST,
        actor=actor,
    )
    step = _confirmation_step(enrollment) if session and not enrollment.is_ended else None
    if step is not None:
        services.move_to_step(enrollment, step, actor)
    return step
