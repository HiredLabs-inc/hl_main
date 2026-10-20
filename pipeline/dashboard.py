"""Queries behind the staff dashboard at /staff/: which enrollments a tab and
its filters show, and the counts in the header strip."""
from collections import defaultdict
from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone

from .models import Activity, Enrollment, Flow, Phase, Step
from .services import can_leave_step

User = get_user_model()

INTAKE = "intake"
MINE = "mine"
ALL = "all"
DEFAULT_STALE_DAYS = 14


class DashboardFilters(forms.Form):
    """GET params, so filtered views can be bookmarked. Blank means "any"."""

    ASSIGNEE_CHOICES = [("", "Anyone"), ("me", "Me"), ("unassigned", "Unassigned")]
    # Blank status means every open enrollment (not completed or withdrawn)
    STATUS_CHOICES = [("", "Open")] + list(Enrollment.Status.choices)

    tab = forms.CharField(required=False, widget=forms.HiddenInput)
    q = forms.CharField(required=False, label="Search", widget=forms.TextInput(attrs={"placeholder": "Name or email"}))
    assignee = forms.ChoiceField(required=False, choices=ASSIGNEE_CHOICES)
    phase = forms.ModelChoiceField(required=False, queryset=Phase.objects.none(), empty_label="Any phase")
    step = forms.ModelChoiceField(required=False, queryset=Step.objects.none(), empty_label="Any step")
    status = forms.ChoiceField(required=False, choices=STATUS_CHOICES)
    days = forms.IntegerField(required=False, min_value=1, label="Days in step over")

    def __init__(self, data, flow=None):
        super().__init__(data)
        if flow is not None:
            self.fields["phase"].queryset = flow.phases.all()
            self.fields["step"].queryset = Step.objects.filter(phase__flow=flow)
        else:
            del self.fields["phase"]
            self.fields["step"].queryset = Step.objects.select_related("phase__flow")
        for field in self.visible_fields():
            field.field.widget.attrs["class"] = "staff-field"
        self.fields["q"].widget.attrs.update({"class": "staff-field w-56", "type": "search"})
        self.fields["days"].widget.attrs["class"] = "staff-field w-24"


def tabs():
    """(slug, label) for Intake, then each other active flow, then My people and Everyone"""
    flows = [(flow.slug, flow.name) for flow in Flow.objects.filter(active=True)]
    flows.sort(key=lambda tab: tab[0] != INTAKE)
    return flows + [(MINE, "My people"), (ALL, "Everyone")]


def open_enrollments():
    return Enrollment.objects.filter(ended_at__isnull=True)


def row_queryset():
    """Enrollments with what a dashboard row shows"""
    last_activity = Activity.objects.filter(person=OuterRef("person")).order_by("-created_at").values("created_at")[:1]
    return Enrollment.objects.select_related(
        "person__profile", "person__participant", "flow", "current_step__phase", "assignee"
    ).annotate(last_activity=Subquery(last_activity))


def decorate(rows, user):
    """Add what each row's controls need, in a fixed number of queries:
    step_choices (the flow's steps), can_leave (the user may move them off
    their current step) and enroll_choices (active flows they could join)."""
    rows = list(rows)
    steps_by_flow = defaultdict(list)
    for step in Step.objects.filter(phase__flow__in={row.flow_id for row in rows}).select_related("phase"):
        steps_by_flow[step.phase.flow_id].append(step)
    open_flows = defaultdict(set)
    for person_id, flow_id in open_enrollments().filter(person__in={row.person_id for row in rows}).values_list(
        "person_id", "flow_id"
    ):
        open_flows[person_id].add(flow_id)
    joinable = [flow for flow in Flow.objects.filter(active=True) if flow.slug != INTAKE]
    for row in rows:
        row.step_choices = steps_by_flow[row.flow_id]
        row.can_leave = can_leave_step(user, row.current_step)
        row.enroll_choices = [flow for flow in joinable if flow.pk not in open_flows[row.person_id]]
    return rows


def staff_users():
    """Who can be assigned"""
    return User.objects.filter(is_staff=True, is_active=True).order_by("first_name", "last_name", "email")


def row(enrollment_pk, user):
    return decorate(row_queryset().filter(pk=enrollment_pk), user)[0]


def enrollments(user, tab, filters):
    """Enrollments for a tab, filtered by a valid DashboardFilters, ready to render"""
    qs = row_queryset()
    if tab == MINE:
        qs = qs.filter(assignee=user)
    elif tab != ALL:
        qs = qs.filter(flow__slug=tab)

    data = filters.cleaned_data
    status = data.get("status")
    qs = qs.filter(status=status) if status else qs.filter(ended_at__isnull=True)
    if data.get("assignee") == "me":
        qs = qs.filter(assignee=user)
    elif data.get("assignee") == "unassigned":
        qs = qs.filter(assignee__isnull=True)
    if data.get("phase"):
        qs = qs.filter(current_step__phase=data["phase"])
    if data.get("step"):
        qs = qs.filter(current_step=data["step"])
    if data.get("days"):
        qs = qs.filter(step_entered_at__lt=timezone.now() - timedelta(days=data["days"]))
    if data.get("q"):
        for word in data["q"].split():
            qs = qs.filter(
                Q(person__first_name__icontains=word)
                | Q(person__last_name__icontains=word)
                | Q(person__email__icontains=word)
            )
    return decorate(
        qs.order_by(
            "flow__order", "current_step__phase__order", "current_step__phase_id",
            "current_step__order", "current_step_id", "step_entered_at",
        ),
        user,
    )


def header_counts():
    """Counts for the strip above the tabs, each with the GET params that show them"""
    intake_steps = (
        Step.objects.filter(phase__flow__slug=INTAKE)
        .annotate(open=Count("enrollments", filter=Q(enrollments__ended_at__isnull=True)))
        .order_by(*Step._meta.ordering)  # Meta.ordering doesn't apply to GROUP BY queries
    )
    counts = [
        {"label": f"In {step.title}", "count": step.open, "params": {"tab": INTAKE, "step": step.pk}}
        for step in intake_steps
    ]
    stale_before = timezone.now() - timedelta(days=DEFAULT_STALE_DAYS)
    totals = open_enrollments().aggregate(
        unassigned=Count("pk", filter=Q(assignee__isnull=True)),
        stale=Count("pk", filter=Q(step_entered_at__lt=stale_before)),
    )
    counts += [
        {"label": "Unassigned", "count": totals["unassigned"], "params": {"tab": ALL, "assignee": "unassigned"}},
        {
            "label": f"In step over {DEFAULT_STALE_DAYS} days",
            "count": totals["stale"],
            "params": {"tab": ALL, "days": DEFAULT_STALE_DAYS},
        },
    ]
    return counts
