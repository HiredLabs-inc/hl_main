"""The only code that changes enrollments. Each function runs in a transaction,
checks the rules, and records what happened on the Activity timeline of the
person or lead enrolled.
Views decide who may call them (pipeline.guards); step permissions and who
can be assigned are checked here.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .guards import can_be_assigned
from .models import Activity, Enrollment, Flow, Step


class AlreadyEnrolled(ValidationError):
    pass


class StaleStep(ValidationError):
    """The enrollment isn't on the step the caller last saw (someone else moved it)"""


def _user_label(user):
    if user is None:
        return ""
    return user.get_full_name() or user.email


def _locked(enrollment):
    """Re-read the enrollment under a row lock so concurrent edits queue up"""
    return Enrollment.objects.select_for_update().get(pk=enrollment.pk)


def _check_open(enrollment):
    if enrollment.is_ended:
        raise ValidationError(f"{enrollment} has ended and can't be changed.")


def _record(enrollment, actor, kind, text="", from_value="", to_value=""):
    return Activity.objects.create(
        person_id=enrollment.person_id,
        lead_id=enrollment.lead_id,
        enrollment=enrollment,
        kind=kind,
        text=text,
        from_value=from_value[:200],
        to_value=to_value[:200],
        actor=actor,
    )


def _assignee_refusal(flow):
    if flow.subject == Flow.Subject.LEAD:
        return "Only active staff and volunteers who work leads can be assigned."
    return "Only active staff can be assigned."


def can_leave_step(user, step):
    return not step.required_permission or user.has_perm(step.required_permission)


@transaction.atomic
def enroll(person, flow: Flow, actor, step: Step = None, assignee=None, lead=None) -> Enrollment:
    """Start person (or, in a lead flow, lead with person=None) on step
    (default: the flow's first step). Raises AlreadyEnrolled if they have an
    open enrollment in this flow."""
    if (person is None) == (lead is None):
        raise ValidationError("Enroll a person or a lead.")
    subject = Flow.Subject.LEAD if lead is not None else Flow.Subject.PERSON
    if flow.subject != subject:
        raise ValidationError(f"{flow} is for {flow.get_subject_display().lower()}.")
    step = step or flow.first_step()
    if step is None:
        raise ValidationError(f"{flow} has no steps.")
    if step.phase.flow_id != flow.pk:
        raise ValidationError(f"{step} isn't part of {flow}.")
    if assignee is not None and not can_be_assigned(assignee, flow):
        raise ValidationError(_assignee_refusal(flow))
    try:
        with transaction.atomic():
            enrollment = Enrollment.objects.create(
                person=person,
                lead=lead,
                flow=flow,
                current_step=step,
                assignee=assignee,
                step_entered_at=timezone.now(),
            )
    except IntegrityError:
        raise AlreadyEnrolled(f"{_user_label(person) if person else lead} is already enrolled in {flow}.")
    _record(enrollment, actor, Activity.Kind.ENROLLED, to_value=step.title)
    if assignee is not None:
        _record(enrollment, actor, Activity.Kind.ASSIGNEE_CHANGE, to_value=_user_label(assignee))
    return enrollment


@transaction.atomic
def move_to_step(enrollment: Enrollment, step: Step, actor, from_step: Step = None) -> Enrollment:
    """With from_step, refuse (StaleStep) unless the enrollment is still on it"""
    enrollment = _locked(enrollment)
    _check_open(enrollment)
    if from_step is not None and enrollment.current_step_id != from_step.pk:
        raise StaleStep(f"{enrollment} is no longer on {from_step.title}.")
    if step.phase.flow_id != enrollment.flow_id:
        raise ValidationError(f"{step} isn't part of {enrollment.flow}.")
    if step.pk == enrollment.current_step_id:
        return enrollment
    previous = enrollment.current_step
    if not can_leave_step(actor, previous):
        raise PermissionDenied(f"Moving someone off {previous.title} needs {previous.required_permission}.")
    enrollment.current_step = step
    enrollment.step_entered_at = timezone.now()
    enrollment.save(update_fields=["current_step", "step_entered_at", "updated_at"])
    _record(enrollment, actor, Activity.Kind.STEP_CHANGE, from_value=previous.title, to_value=step.title)
    return enrollment


@transaction.atomic
def assign(enrollment: Enrollment, assignee, actor) -> Enrollment:
    """Set or clear (assignee=None) who is responsible for this enrollment"""
    enrollment = _locked(enrollment)
    _check_open(enrollment)
    if assignee is not None and not can_be_assigned(assignee, enrollment.flow):
        raise ValidationError(_assignee_refusal(enrollment.flow))
    if enrollment.assignee_id == (assignee.pk if assignee else None):
        return enrollment
    previous = enrollment.assignee
    enrollment.assignee = assignee
    enrollment.save(update_fields=["assignee", "updated_at"])
    _record(
        enrollment,
        actor,
        Activity.Kind.ASSIGNEE_CHANGE,
        from_value=_user_label(previous),
        to_value=_user_label(assignee),
    )
    return enrollment


# Functions (enrollment, refusals) that adjust ending_options for a flow, e.g.
# Boot Camp's session rules; userprofile registers its own when the app loads
STATUS_RULES = []


def ending_options(enrollment: Enrollment, steps=None) -> dict:
    """{status: refusal} for each status that ends an enrollment; a blank refusal
    means it's allowed. Completed needs a final step (completes_flow); Dropped
    is refused unless a flow's rule allows it. steps (the flow's steps, if the
    caller has them) saves a query."""
    flow = enrollment.flow
    refusals = dict.fromkeys(Enrollment.ENDED_STATUSES, "")
    if not enrollment.current_step.completes_flow:
        if steps is None:
            steps = Step.objects.filter(phase__flow_id=enrollment.flow_id)
        final = next((step for step in steps if step.completes_flow), None)
        refusals[Enrollment.Status.COMPLETED] = (
            f"Move them to {final.title} first." if final else f"{flow} enrollments can't be completed; withdraw instead."
        )
    refusals[Enrollment.Status.DROPPED] = f"{flow} enrollments can't be dropped; withdraw instead."
    for rule in STATUS_RULES:
        rule(enrollment, refusals)
    return refusals


def ending_choices(enrollment: Enrollment, steps=None) -> list:
    """The statuses this enrollment can end with (or switch to, if it has ended)"""
    refusals = ending_options(enrollment, steps)
    return [status for status in Enrollment.Status if status in refusals and not refusals[status] and status != enrollment.status]


def _change_status(enrollment, status, actor, reason=""):
    if status == enrollment.status:
        return enrollment
    previous = enrollment.get_status_display()
    enrollment.status = status
    if status in Enrollment.ENDED_STATUSES and enrollment.ended_at is None:
        enrollment.ended_at = timezone.now()
    enrollment.save(update_fields=["status", "ended_at", "updated_at"])
    _record(
        enrollment,
        actor,
        Activity.Kind.STATUS_CHANGE,
        text=reason,
        from_value=previous,
        to_value=enrollment.get_status_display(),
    )
    return enrollment


@transaction.atomic
def set_status(enrollment: Enrollment, status, actor, reason="") -> Enrollment:
    """Completed, withdrawn and dropped end the enrollment, when ending_options
    allows it; an ended enrollment can switch between them, keeping its end
    date. Rejected needs a reason (e.g. "unclear DD214"), which is kept on the
    timeline."""
    status = Enrollment.Status(status)
    enrollment = _locked(enrollment)
    ending = status in Enrollment.ENDED_STATUSES
    if enrollment.is_ended and not ending:
        raise ValidationError(f"{enrollment} has ended. Reopen it first.")
    reason = reason.strip()
    if status == Enrollment.Status.REJECTED and not reason:
        raise ValidationError("Give a reason for the rejection.")
    if status == enrollment.status:
        return enrollment
    if ending:
        refusal = ending_options(enrollment)[status]
        if refusal:
            raise ValidationError(refusal)
    return _change_status(enrollment, status, actor, reason)


@transaction.atomic
def reopen(enrollment: Enrollment, actor, reason="") -> Enrollment:
    """Make an ended enrollment active again, e.g. to fix a mistaken ending.
    Raises AlreadyEnrolled if the person has since been enrolled in the flow again."""
    enrollment = _locked(enrollment)
    if not enrollment.is_ended:
        return enrollment
    previous = enrollment.get_status_display()
    enrollment.status = Enrollment.Status.ACTIVE
    enrollment.ended_at = None
    try:
        with transaction.atomic():
            enrollment.save(update_fields=["status", "ended_at", "updated_at"])
    except IntegrityError:
        raise AlreadyEnrolled(
            f"{enrollment.label} already has an open {enrollment.flow} enrollment, so this one can't be reopened."
        )
    _record(
        enrollment,
        actor,
        Activity.Kind.STATUS_CHANGE,
        text=reason.strip() or "Reopened",
        from_value=previous,
        to_value=enrollment.get_status_display(),
    )
    return enrollment


def add_note(person, actor, text, kind=Activity.Kind.NOTE, enrollment: Enrollment = None, lead=None) -> Activity:
    """A note or a record of contact (email, phone, in person) about a person,
    or a lead (person=None)"""
    if kind not in Activity.CONTACT_KINDS:
        raise ValidationError(f"{kind} entries are recorded automatically.")
    text = text.strip()
    if not text:
        raise ValidationError("A note needs some text.")
    if (person is None) == (lead is None):
        raise ValidationError("A note is about a person or a lead.")
    if enrollment is not None and (enrollment.person_id, enrollment.lead_id) != (
        person.pk if person else None,
        lead.pk if lead else None,
    ):
        raise ValidationError("That enrollment belongs to someone else.")
    return Activity.objects.create(person=person, lead=lead, enrollment=enrollment, kind=kind, text=text, actor=actor)


def record_document_opened(person, actor, document):
    """Audit entry for opening a sensitive document such as a DD214"""
    return Activity.objects.create(
        person=person, kind=Activity.Kind.DOCUMENT_OPENED, text=document, actor=actor
    )


@transaction.atomic
def complete_triage(intake: Enrollment, flows, actor):
    """Enroll the person in each flow (skipping ones they're already in), then
    complete their Intake enrollment. Returns the new enrollments."""
    intake = _locked(intake)
    _check_open(intake)
    if not can_leave_step(actor, intake.current_step):
        raise PermissionDenied(
            f"Moving someone off {intake.current_step.title} needs {intake.current_step.required_permission}."
        )
    created = []
    for flow in flows:
        if flow.pk == intake.flow_id:
            continue
        if Enrollment.objects.filter(person_id=intake.person_id, flow=flow, ended_at__isnull=True).exists():
            continue
        created.append(enroll(intake.person, flow, actor))
    # Triage is how Intake ends, so it skips the final-step check
    _change_status(intake, Enrollment.Status.COMPLETED, actor)
    return created
