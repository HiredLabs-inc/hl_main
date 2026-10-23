"""htmx endpoints behind the dashboard's row controls and side panel. Each one
calls a pipeline.services function and answers with the updated row (or
panel). Success triggers "enrollment-changed" so the dashboard refreshes its
table and counts; refusals leave the page as it is and show a toast.
Staff may use them all; volunteers with work_lead_flows may move, assign,
change the status of, reopen and add notes to lead enrollments (pipeline.guards)."""
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince
from django.views.decorators.http import require_GET, require_POST

from userprofile import bootcamp
from userprofile.guards import staff_required

from . import dashboard, services
from .guards import enrollment_worker_required
from .models import Activity, Enrollment, Flow, Step

User = get_user_model()
CHANGED = "enrollment-changed"
TIMELINE_LENGTH = 50


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _toast(response, text, category="success", changed=False):
    events = {"toast": {"category": category, "text": text}}
    if changed:
        events[CHANGED] = True
    response["HX-Trigger"] = json.dumps(events)
    return response


def _refused(request, error):
    """Keep the page as it is and say why"""
    messages = error.messages if isinstance(error, ValidationError) else [str(error) or "You can't do that."]
    response = render(request, "pipeline/partials/empty.html")
    response["HX-Reswap"] = "none"
    return _toast(response, " ".join(messages), category="error")


def _row(request, enrollment, text):
    response = render(
        request,
        "pipeline/partials/enrollment_row.html",
        {
            "enrollment": dashboard.row(enrollment.pk, request.user),
            "stale_days": dashboard.DEFAULT_STALE_DAYS,
            "staff_users": dashboard.staff_users(enrollment.flow),
        },
    )
    return _toast(response, text, changed=True)


def _act(request, enrollment_pk, action):
    """Run action(enrollment) -> success text, answering with the row or a refusal"""
    enrollment = get_object_or_404(Enrollment, pk=enrollment_pk)
    try:
        text = action(enrollment)
    except (ValidationError, PermissionDenied) as error:
        return _refused(request, error)
    return _row(request, enrollment, text)


def _leave_refusal(step):
    if step.required_permission == "userprofile.review_veteran_status":
        return f"Only veteran reviewers can move people off {step.title}."
    return f"You can't move people off {step.title}."


@require_POST
@enrollment_worker_required
def move_view(request, enrollment_pk):
    """Move to POST step. from_step (the step the page showed) refuses the move
    if someone else has moved them since. render=card answers for the board."""
    if request.POST.get("render") == "card":
        return _move_card(request, enrollment_pk)

    def action(enrollment):
        step = Step.objects.filter(pk=_int(request.POST.get("step"))).first()
        if step is None:
            raise ValidationError("Choose a step.")
        from_step = Step.objects.filter(pk=_int(request.POST.get("from_step"))).first()
        try:
            services.move_to_step(enrollment, step, request.user, from_step=from_step)
        except PermissionDenied:
            raise PermissionDenied(_leave_refusal(enrollment.current_step))
        except services.StaleStep:
            raise ValidationError(_stale_text(enrollment) + " Refresh to see where they are now.")
        return f"Moved to {step.title}."

    return _act(request, enrollment_pk, action)


def _stale_text(enrollment):
    """Who moved them where, from their latest step change"""
    enrollment.refresh_from_db()
    name = (enrollment.person.first_name or enrollment.person.email) if enrollment.person_id else enrollment.label
    change = enrollment.activities.filter(kind=Activity.Kind.STEP_CHANGE).select_related("actor").first()
    where = enrollment.current_step.title
    if change is None:
        return f"Someone else moved {name} to {where}."
    who = (change.actor.get_full_name() or change.actor.email) if change.actor else ""
    recent = timezone.now() - change.created_at < timedelta(minutes=1)
    when = "just now" if recent else f"{timesince(change.created_at).split(',')[0]} ago"
    return f"{who or 'Someone'} moved {name} to {where} {when}."


def _move_card(request, enrollment_pk):
    """The board's move: answers with the card as it now is, recounted columns,
    and a status the board script uses. 200 moved (toast with Undo); 409 moved
    by someone else since the board loaded; 403 the user may not move them off
    their step; 400 bad step or the enrollment has ended (the card goes)."""
    enrollment = get_object_or_404(Enrollment.objects.select_related("person", "lead", "current_step"), pk=enrollment_pk)
    from_step = enrollment.current_step
    step = Step.objects.filter(pk=_int(request.POST.get("step")), phase__flow=enrollment.flow_id).first()
    shown_step = Step.objects.filter(pk=_int(request.POST.get("from_step"))).first()
    status, error = 200, ""
    if enrollment.is_ended:
        status, error = 400, "This enrollment has ended."
    elif step is None:
        status, error = 400, "Choose a step in this flow."
    else:
        try:
            services.move_to_step(enrollment, step, request.user, from_step=shown_step)
        except services.StaleStep:
            status, error = 409, _stale_text(enrollment)
        except PermissionDenied:
            status, error = 403, _leave_refusal(from_step)
        except ValidationError as refusal:
            status, error = 400, " ".join(refusal.messages)
    return _card(request, enrollment, status, error, steps=[s for s in (from_step, shown_step, step) if s])


def _card(request, enrollment, status, error, steps):
    flow = enrollment.flow
    filters = dashboard.page_filters(request.headers.get("HX-Current-URL"), flow)
    card = dashboard.card(enrollment.pk, request.user)
    if card is not None:
        steps.append(card.current_step)
    step_counts, phase_counts = dashboard.board_counts(request.user, flow, filters, set(steps))
    context = {
        "flow": flow,
        "enrollment": card,
        "compact": card is not None and step_counts[card.current_step_id] > dashboard.BOARD_COMPACT_OVER,
        "moved": status == 200,
        "error": error if card is not None else "",
        "step_counts": step_counts,
        "phase_counts": phase_counts,
        "stale_days": dashboard.DEFAULT_STALE_DAYS,
    }
    response = render(request, "pipeline/partials/board_move.html", context, status=status)
    # Tells the board script to swap refusals too: they carry the card as it is
    response["HX-Board-Card"] = "true"
    events = {"board-changed": True}
    if status == 200:
        name = enrollment.label
        events["toast"] = {
            "category": "success",
            "text": f"Moved {name} to {card.current_step.title}.",
            "undo": {
                "url": reverse("pipeline:move", args=[enrollment.pk]),
                "card": f"card-{enrollment.pk}",
                "values": {"step": steps[0].pk, "from_step": card.current_step_id, "render": "card"},
            },
        }
    elif card is None:
        events["toast"] = {"category": "error", "text": error}
    response["HX-Trigger"] = json.dumps(events)
    return response


@require_POST
@enrollment_worker_required
def assign_view(request, enrollment_pk):
    def action(enrollment):
        pk = request.POST.get("assignee")
        assignee = User.objects.filter(pk=_int(pk)).first() if pk else None
        if pk and assignee is None:
            raise ValidationError("Choose someone to assign.")
        services.assign(enrollment, assignee, request.user)
        return f"Assigned to {assignee.get_full_name() or assignee.email}." if assignee else "Unassigned."

    return _act(request, enrollment_pk, action)


@require_POST
@enrollment_worker_required
def status_view(request, enrollment_pk):
    def action(enrollment):
        if request.POST.get("status") not in Enrollment.Status.values:
            raise ValidationError("Unknown status.")
        enrollment = services.set_status(
            enrollment, request.POST["status"], request.user, reason=request.POST.get("reason", "")
        )
        return f"Status set to {enrollment.get_status_display()}."

    return _act(request, enrollment_pk, action)


@require_POST
@enrollment_worker_required
def reopen_view(request, enrollment_pk):
    def action(enrollment):
        services.reopen(enrollment, request.user)
        return f"Reopened {enrollment.flow.name}."

    return _act(request, enrollment_pk, action)


@require_POST
@staff_required
def session_view(request, enrollment_pk):
    """Place a Boot Camp enrollment in a session, or back on the waitlist (blank)"""

    def action(enrollment):
        pk = request.POST.get("session")
        session = bootcamp.BootCampSession.objects.filter(pk=_int(pk)).first() if pk else None
        if pk and session is None:
            raise ValidationError("Choose a session.")
        moved_to = bootcamp.assign_session(enrollment, session, request.user)
        if session is None:
            return "Moved to the waitlist."
        return f"Session set: {session.label}." + (f" Moved to {moved_to.title}." if moved_to else "")

    return _act(request, enrollment_pk, action)


@require_POST
@enrollment_worker_required
def note_view(request, enrollment_pk):
    def action(enrollment):
        services.add_note(
            enrollment.person,
            request.user,
            request.POST.get("text", ""),
            kind=request.POST.get("kind") or Activity.Kind.NOTE,
            enrollment=enrollment,
            lead=enrollment.lead,
        )
        return "Note added."

    return _act(request, enrollment_pk, action)


def _flows(request):
    """The active people flows ticked in a form"""
    pks = [pk for pk in map(_int, request.POST.getlist("flows")) if pk]
    return list(Flow.objects.for_people().filter(pk__in=pks, active=True))


def _enroll_all(person, flows, actor):
    if not flows:
        raise ValidationError("Choose at least one flow.")
    created = []
    for flow in flows:
        try:
            created.append(services.enroll(person, flow, actor))
        except services.AlreadyEnrolled:
            pass
    return created


@require_POST
@staff_required
def enroll_view(request, enrollment_pk):
    """Enroll the row's person in more flows"""

    def action(enrollment):
        if enrollment.person_id is None:
            raise ValidationError("Leads join their flow when they're approved.")
        created = _enroll_all(enrollment.person, _flows(request), request.user)
        return "Enrolled in " + ", ".join(e.flow.name for e in created) + "." if created else "Already enrolled."

    return _act(request, enrollment_pk, action)


@require_POST
@staff_required
def triage_view(request, enrollment_pk):
    """Enroll in the chosen flows and complete the Intake enrollment"""

    def action(enrollment):
        if enrollment.flow.slug != dashboard.INTAKE:
            raise ValidationError("Only Intake enrollments are triaged.")
        flows = _flows(request)
        if not flows:
            raise ValidationError("Choose at least one flow.")
        created = services.complete_triage(enrollment, flows, request.user)
        names = ", ".join(e.flow.name for e in created)
        return f"Triaged into {names}." if names else "Triaged; they were already in those flows."

    return _act(request, enrollment_pk, action)


def timeline_context(person):
    """What pipeline/partials/timeline.html needs"""
    return {
        "person": person,
        "timeline": person.activities.select_related("actor", "enrollment__flow").prefetch_related("actor__groups")[
            :TIMELINE_LENGTH
        ],
        "note_kinds": [(kind, Activity.Kind(kind).label) for kind in Activity.Kind if kind in Activity.CONTACT_KINDS],
    }


@require_GET
@staff_required
def panel_view(request, user_pk):
    person = get_object_or_404(User.objects.select_related("profile"), pk=user_pk)
    try:
        profile = person.profile
    except ObjectDoesNotExist:
        profile = None
    enrollments = list(
        person.enrollments.select_related("flow", "current_step__phase", "assignee").order_by("ended_at", "flow__order")
    )
    bootcamp.add_sessions(enrollments)
    context = {
        **timeline_context(person),
        "profile": profile,
        "enrollments": enrollments,
    }
    return render(request, "pipeline/partials/person_panel.html", context)


@require_POST
@staff_required
def person_note_view(request, user_pk):
    """A note about the person, not tied to one enrollment; answers with their timeline"""
    person = get_object_or_404(User, pk=user_pk)
    try:
        services.add_note(
            person, request.user, request.POST.get("text", ""), kind=request.POST.get("kind") or Activity.Kind.NOTE
        )
    except ValidationError as error:
        return _refused(request, error)
    response = render(request, "pipeline/partials/timeline.html", timeline_context(person))
    return _toast(response, "Note added.", changed=True)


@require_POST
@staff_required
def person_enroll_view(request, user_pk):
    """Enroll someone in flows from their workspace (any active flow, Intake included)"""
    person = get_object_or_404(User, pk=user_pk)
    try:
        created = _enroll_all(person, _flows(request), request.user)
    except ValidationError as error:
        return _refused(request, error)
    response = render(request, "pipeline/partials/empty.html")
    response["HX-Reswap"] = "none"
    text = "Enrolled in " + ", ".join(e.flow.name for e in created) + "." if created else "Already enrolled."
    return _toast(response, text, changed=bool(created))
