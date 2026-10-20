"""Staff pages about people: search everyone at /staff/people/, and one person's
workspace at /staff/people/<pk>/ (profile, flows, veteran status, timeline and
links to the cold_apply work tools)."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from hl_main.gcs import SIGNED_URL_EXPIRATION, generate_signed_url
from pipeline import dashboard
from pipeline.actions import timeline_context
from pipeline.models import Enrollment, Flow
from resume.models import Education, Experience

from .guards import can_review_veteran_status, staff_required

User = get_user_model()
PAGE_SIZE = 50
RECENT_EXPERIENCES = 3


def _related(obj, name):
    """obj.name for a reverse one-to-one, or None when there isn't one"""
    try:
        return getattr(obj, name)
    except ObjectDoesNotExist:
        return None


@staff_required
def people_view(request):
    """Everyone who has signed up or been in a flow, newest first"""
    open_enrollments = Enrollment.objects.filter(ended_at__isnull=True).select_related("flow", "current_step")
    people = (
        User.objects.filter(is_staff=False)
        .filter(Q(profile__isnull=False) | Q(enrollments__isnull=False))
        .distinct()
        .select_related("profile")
        .prefetch_related(Prefetch("enrollments", queryset=open_enrollments, to_attr="open_enrollments"))
        .order_by("-date_joined", "-pk")
    )
    query = request.GET.get("q", "").strip()
    for word in query.split():
        people = people.filter(
            Q(first_name__icontains=word) | Q(last_name__icontains=word) | Q(email__icontains=word)
        )
    page = Paginator(people, PAGE_SIZE).get_page(request.GET.get("page"))
    template = "userprofile/people/people_table.html" if request.headers.get("HX-Request") else "userprofile/people/people.html"
    return render(request, template, {"page": page, "q": query})


def _resume_url(profile):
    if profile is None or not profile.resume:
        return None
    if settings.DEBUG:
        return profile.resume.url
    return generate_signed_url(
        bucket_name=settings.GS_BUCKET_NAME, object_name=profile.resume.name, expiration=SIGNED_URL_EXPIRATION
    )


def _flows_context(request, person):
    rows = dashboard.decorate(
        dashboard.row_queryset().filter(person=person).order_by("ended_at", "flow__order", "-created_at"),
        request.user,
    )
    open_flow_ids = {row.flow_id for row in rows if not row.is_ended}
    in_intake = any(row.flow.slug == dashboard.INTAKE and not row.is_ended for row in rows)
    return {
        "person": person,
        "rows": rows,
        "staff_users": dashboard.staff_users(),
        "stale_days": dashboard.DEFAULT_STALE_DAYS,
        # Someone in Intake joins other flows through triage, after veteran review
        "joinable_flows": []
        if in_intake
        else [flow for flow in Flow.objects.filter(active=True) if flow.pk not in open_flow_ids],
    }


@staff_required
def person_view(request, user_pk):
    person = get_object_or_404(User.objects.select_related("profile", "participant"), pk=user_pk)
    if person.is_staff:
        raise Http404
    part = request.GET.get("part")
    if part == "flows":
        return render(request, "userprofile/people/person_flows.html", _flows_context(request, person))
    if part == "timeline":
        return render(request, "pipeline/partials/timeline.html", timeline_context(person))

    profile = _related(person, "profile")
    participant = _related(person, "participant")
    context = {
        **_flows_context(request, person),
        **timeline_context(person),
        "profile": profile,
        "veteran_profile": _related(person, "veteranprofile"),
        "participant": participant,
        "can_review": can_review_veteran_status(request.user),
        "resume_url": _resume_url(profile),
        "experiences": Experience.objects.filter(participant=participant).select_related("org", "position")[
            :RECENT_EXPERIENCES
        ]
        if participant
        else [],
        "educations": Education.objects.filter(participant=participant).select_related(
            "org", "degree", "concentration"
        )
        if participant
        else [],
    }
    return render(request, "userprofile/people/person.html", context)
