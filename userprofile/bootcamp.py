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


def upcoming_sessions():
    """Sessions people can still be placed in"""
    return BootCampSession.objects.filter(start_date__gte=timezone.localdate())


def add_sessions(enrollments):
    """Set session (None means waitlist) and session_choices on each Boot Camp
    enrollment, in two queries. The choices are the upcoming sessions, plus the
    current one if it has already started."""
    enrollments = [enrollment for enrollment in enrollments if is_boot_camp(enrollment)]
    if not enrollments:
        return
    seats = BootCampSeat.objects.filter(enrollment__in=enrollments).select_related("session")
    sessions = {seat.enrollment_id: seat.session for seat in seats}
    upcoming = list(upcoming_sessions())
    for enrollment in enrollments:
        enrollment.session = sessions.get(enrollment.pk)
        current = [enrollment.session] if enrollment.session and enrollment.session not in upcoming else []
        enrollment.session_choices = current + upcoming


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
    also moves them on to Send Enrollment Confirmation (see _confirmation_step);
    returns that step if they moved, otherwise None."""
    enrollment = Enrollment.objects.select_for_update(of=("self",)).select_related("flow").get(pk=enrollment.pk)
    if not is_boot_camp(enrollment):
        raise ValidationError("Only Boot Camp enrollments have sessions.")
    if enrollment.is_ended:
        raise ValidationError(f"This enrollment has ended ({enrollment.get_status_display().lower()}).")
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
    step = _confirmation_step(enrollment) if session else None
    if step is not None:
        services.move_to_step(enrollment, step, actor)
    return step
