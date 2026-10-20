"""htmx endpoints behind the dashboard's row controls and side panel. Each one
calls a pipeline.services function and answers with the updated row (or
panel). Success triggers "enrollment-changed" so the dashboard refreshes its
table and counts; refusals leave the page as it is and show a toast."""
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from userprofile.guards import staff_required

from . import dashboard, services
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
            "staff_users": dashboard.staff_users(),
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


@require_POST
@staff_required
def move_view(request, enrollment_pk):
    def action(enrollment):
        step = Step.objects.filter(pk=_int(request.POST.get("step"))).first()
        if step is None:
            raise ValidationError("Choose a step.")
        services.move_to_step(enrollment, step, request.user)
        return f"Moved to {step.title}."

    return _act(request, enrollment_pk, action)


@require_POST
@staff_required
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
@staff_required
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
@staff_required
def note_view(request, enrollment_pk):
    def action(enrollment):
        services.add_note(
            enrollment.person,
            request.user,
            request.POST.get("text", ""),
            kind=request.POST.get("kind") or Activity.Kind.NOTE,
            enrollment=enrollment,
        )
        return "Note added."

    return _act(request, enrollment_pk, action)


def _flows(request):
    """The active flows ticked in a form"""
    return list(Flow.objects.filter(pk__in=[pk for pk in map(_int, request.POST.getlist("flows")) if pk], active=True))


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
        "timeline": person.activities.select_related("actor", "enrollment__flow")[:TIMELINE_LENGTH],
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
    context = {
        **timeline_context(person),
        "profile": profile,
        "enrollments": person.enrollments.select_related("flow", "current_step__phase", "assignee").order_by(
            "ended_at", "flow__order"
        ),
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
