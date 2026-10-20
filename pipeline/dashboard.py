"""Queries behind the staff dashboard at /staff/: which enrollments a tab and
its filters show, and the counts in the header strip."""
from collections import defaultdict
from urllib.parse import urlsplit
from dataclasses import dataclass, field
from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import QueryDict
from django.utils import timezone

from userprofile import bootcamp

from .models import Activity, Enrollment, Flow, Phase, Step
from .services import can_leave_step

User = get_user_model()

INTAKE = "intake"
MINE = "mine"
ALL = "all"
DEFAULT_STALE_DAYS = 14
TABLE = "table"
BOARD = "board"
# Cards a board column shows at first and per "Show more"
BOARD_PAGE = 25
# Columns with more cards than this show one-line cards
BOARD_COMPACT_OVER = 30


class DashboardFilters(forms.Form):
    """GET params, so filtered views can be bookmarked. Blank means "any"."""

    ASSIGNEE_CHOICES = [("", "Anyone"), ("me", "Me"), ("unassigned", "Unassigned")]
    # Blank status means every open enrollment (not completed or withdrawn)
    STATUS_CHOICES = [("", "Open")] + list(Enrollment.Status.choices)

    tab = forms.CharField(required=False, widget=forms.HiddenInput)
    view = forms.CharField(required=False, widget=forms.HiddenInput)
    q = forms.CharField(required=False, label="Search", widget=forms.TextInput(attrs={"placeholder": "Name or email"}))
    assignee = forms.ChoiceField(required=False, choices=ASSIGNEE_CHOICES)
    phase = forms.ModelChoiceField(required=False, queryset=Phase.objects.none(), empty_label="Any phase")
    step = forms.ModelChoiceField(required=False, queryset=Step.objects.none(), empty_label="Any step")
    status = forms.ChoiceField(required=False, choices=STATUS_CHOICES)
    days = forms.IntegerField(required=False, min_value=1, label="Days in step over")
    # Boot Camp tab only: "waitlist" or a session pk
    session = forms.ChoiceField(required=False)

    def __init__(self, data, flow=None):
        super().__init__(data)
        if flow is not None:
            self.fields["phase"].queryset = flow.phases.all()
            self.fields["step"].queryset = Step.objects.filter(phase__flow=flow)
        else:
            del self.fields["phase"]
            self.fields["step"].queryset = Step.objects.select_related("phase__flow")
        if flow is not None and flow.slug == bootcamp.FLOW_SLUG:
            self.fields["session"].choices = [("", "Any session"), ("waitlist", bootcamp.WAITLIST)] + [
                (str(session.pk), session.label) for session in bootcamp.BootCampSession.objects.all()
            ]
        else:
            del self.fields["session"]
        for field in self.visible_fields():
            field.field.widget.attrs["class"] = "staff-field"
        self.fields["q"].widget.attrs.update({"class": "staff-field w-56", "type": "search"})
        self.fields["days"].widget.attrs["class"] = "staff-field w-24"


def tabs():
    """(slug, label) for Intake, then each other active flow, then My people and Everyone"""
    flows = [(flow.slug, flow.name) for flow in Flow.objects.filter(active=True)]
    flows.sort(key=lambda tab: tab[0] != INTAKE)
    return flows + [(MINE, "My people"), (ALL, "Everyone")]


def has_board(flow):
    """Flow tabs get a board; Intake (triage needs its form) and the mixed tabs don't"""
    return flow is not None and flow.slug != INTAKE


def initials(user):
    letters = (user.first_name[:1] + user.last_name[:1]) or user.email[:1]
    return letters.upper()


def open_enrollments():
    return Enrollment.objects.filter(ended_at__isnull=True)


def row_queryset():
    """Enrollments with what a dashboard row shows"""
    last_activity = Activity.objects.filter(person=OuterRef("person")).order_by("-created_at").values("created_at")[:1]
    return Enrollment.objects.select_related(
        "person__profile", "flow", "current_step__phase", "assignee"
    ).annotate(last_activity=Subquery(last_activity))


def decorate(rows, user):
    """Add what each row's controls need, in a fixed number of queries:
    step_choices (the flow's steps), can_leave (the user may move them off
    their current step) and enroll_choices (active flows they could join).
    Boot Camp rows also get session (None means waitlist) and session_choices."""
    rows = list(rows)
    steps_by_flow = defaultdict(list)
    for step in Step.objects.filter(phase__flow__in={row.flow_id for row in rows}).select_related("phase"):
        steps_by_flow[step.phase.flow_id].append(step)
    open_flows = defaultdict(dict)
    for person_id, flow_id, flow_name in open_enrollments().filter(
        person__in={row.person_id for row in rows}
    ).values_list("person_id", "flow_id", "flow__name"):
        open_flows[person_id][flow_id] = flow_name
    joinable = [flow for flow in Flow.objects.filter(active=True) if flow.slug != INTAKE]
    bootcamp.add_sessions(rows)
    for row in rows:
        row.step_choices = steps_by_flow[row.flow_id]
        row.can_leave = can_leave_step(user, row.current_step)
        row.enroll_choices = [flow for flow in joinable if flow.pk not in open_flows[row.person_id]]
        row.also_in = [name for flow_id, name in open_flows[row.person_id].items() if flow_id != row.flow_id]
    return rows


def staff_users():
    """Who can be assigned"""
    return User.objects.filter(is_staff=True, is_active=True).order_by("first_name", "last_name", "email")


def row(enrollment_pk, user):
    return decorate(row_queryset().filter(pk=enrollment_pk), user)[0]


def enrollments(user, tab, filters):
    """Enrollments for a tab, filtered by a valid DashboardFilters, ready to render"""
    return decorate(filtered(row_queryset(), user, tab, filters), user)


def filtered(qs, user, tab, filters):
    """qs narrowed to a tab and a valid DashboardFilters, in table order (by step, oldest in step first)"""
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
    if data.get("session") == "waitlist":
        qs = qs.filter(bootcamp_seat__isnull=True)
    elif data.get("session"):
        qs = qs.filter(bootcamp_seat__session_id=data["session"])
    if data.get("days"):
        qs = qs.filter(step_entered_at__lt=timezone.now() - timedelta(days=data["days"]))
    if data.get("q"):
        for word in data["q"].split():
            qs = qs.filter(
                Q(person__first_name__icontains=word)
                | Q(person__last_name__icontains=word)
                | Q(person__email__icontains=word)
            )
    return qs.order_by(
        "flow__order", "current_step__phase__order", "current_step__phase_id",
        "current_step__order", "current_step_id", "step_entered_at",
    )


@dataclass
class Column:
    """One step on a board. cards are the first ones shown (or the page after
    offset); count is how many match the filters; open is everyone on the step,
    whatever the filters, so filtering doesn't collapse columns."""

    step: Step
    cards: list
    count: int
    open: int
    offset: int = 0

    @property
    def next_offset(self):
        return self.offset + len(self.cards)

    @property
    def more(self):
        return self.count - self.next_offset

    @property
    def next_page(self):
        return min(self.more, BOARD_PAGE)

    @property
    def count_title(self):
        return f"{self.count} of {self.open} match the filters" if self.count != self.open else ""

    @property
    def compact(self):
        return self.count > BOARD_COMPACT_OVER

    @property
    def waiting_on_participant(self):
        return self.step.owner == Step.Owner.PARTICIPANT


@dataclass
class BoardPhase:
    phase: Phase
    columns: list = field(default_factory=list)

    @property
    def count(self):
        return sum(column.count for column in self.columns)


def card_queryset():
    """Open enrollments with what a board card shows: row_queryset, plus the
    last activity's kind and the enrollment's latest status change reason"""
    last_kind = Activity.objects.filter(person=OuterRef("person")).order_by("-created_at").values("kind")[:1]
    reason = (
        Activity.objects.filter(enrollment=OuterRef("pk"), kind=Activity.Kind.STATUS_CHANGE)
        .order_by("-created_at")
        .values("text")[:1]
    )
    return row_queryset().filter(ended_at__isnull=True).annotate(
        last_activity_kind=Subquery(last_kind), status_reason=Subquery(reason)
    )


def cards(rows, user):
    rows = decorate(rows, user)
    now = timezone.now()
    for row in rows:
        row.last_activity_days = (now - row.last_activity).days if row.last_activity else None
        row.last_activity_label = Activity.Kind(row.last_activity_kind).label if row.last_activity_kind else ""
        # A soft rejection shows its reason ("Unclear DD214") while it's the latest activity
        rejected = row.status == Enrollment.Status.REJECTED and row.last_activity_kind == Activity.Kind.STATUS_CHANGE
        if rejected and row.status_reason:
            row.last_activity_label = row.status_reason
        row.assignee_initials = initials(row.assignee) if row.assignee else ""
    return rows


def board(user, flow, filters):
    """A flow's open enrollments by step, under phase headings, for a valid
    DashboardFilters. Ended enrollments are never on a board. The phase filter
    hides the other phases; the other filters only hide cards."""
    by_step = defaultdict(list)
    for card in cards(filtered(card_queryset(), user, flow.slug, filters), user):
        by_step[card.current_step_id].append(card)
    steps = (
        Step.objects.filter(phase__flow=flow)
        .select_related("phase")
        .annotate(open=Count("enrollments", filter=Q(enrollments__ended_at__isnull=True)))
        .order_by(*Step._meta.ordering)  # Meta.ordering doesn't apply to GROUP BY queries
    )
    phase_filter = filters.cleaned_data.get("phase")
    phases = {}
    for step in steps:
        if phase_filter and step.phase_id != phase_filter.pk:
            continue
        found = by_step[step.pk]
        column = Column(step, found[:BOARD_PAGE], len(found), step.open)
        phases.setdefault(step.phase_id, BoardPhase(step.phase)).columns.append(column)
    return list(phases.values())


def card(enrollment_pk, user):
    """One board card, or None if the enrollment has ended"""
    found = cards(card_queryset().filter(pk=enrollment_pk), user)
    return found[0] if found else None


def page_filters(url, flow):
    """DashboardFilters from the URL of the page a request came from (htmx's
    HX-Current-URL), so a board action can recount with the board's filters"""
    filters = DashboardFilters(QueryDict(urlsplit(url or "").query), flow=flow)
    return filters if filters.is_valid() else DashboardFilters({}, flow=flow)


def board_counts(user, flow, filters, steps):
    """Card counts matching a valid DashboardFilters, for steps and their phases:
    ({step pk: count}, {phase pk: count})"""
    qs = filtered(open_enrollments(), user, flow.slug, filters).order_by()
    step_counts = dict.fromkeys((step.pk for step in steps), 0)
    step_counts.update(
        qs.filter(current_step__in=steps).values("current_step").annotate(n=Count("pk")).values_list("current_step", "n")
    )
    phase_counts = dict.fromkeys((step.phase_id for step in steps), 0)
    phase_counts.update(
        qs.filter(current_step__phase__in=phase_counts)
        .values("current_step__phase")
        .annotate(n=Count("pk"))
        .values_list("current_step__phase", "n")
    )
    return step_counts, phase_counts


def board_column(user, flow, step, filters, offset):
    """The page of a board column after offset ("Show more")"""
    qs = filtered(card_queryset(), user, flow.slug, filters).filter(current_step=step)
    return Column(step, cards(qs[offset : offset + BOARD_PAGE], user), qs.count(), 0, offset)


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
