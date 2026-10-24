"""Queries behind the staff dashboard at /staff/: which enrollments a tab and
its filters show, and the counts in the header strip."""
from collections import defaultdict
from urllib.parse import urlsplit
from dataclasses import dataclass, field
from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import QueryDict
from django.utils import timezone

from userprofile import bootcamp

from .guards import can_work_lead_flows, lead_workers_q
from .models import Activity, Enrollment, Flow, Phase, Step
from .services import can_leave_step, ending_choices

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
    # Blank status means every open enrollment (not completed, withdrawn or dropped)
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


def tabs(user=None):
    """(slug, label) for Intake, then each other active people flow, My people
    and Everyone, then the active lead flows (Funding, Outreach). With user,
    only the tabs they may see: everything for staff, the lead flows for
    volunteers with work_lead_flows."""
    active = Flow.objects.filter(active=True)
    leads = [(flow.slug, flow.name) for flow in active.filter(subject=Flow.Subject.LEAD)]
    if user is not None and not user.is_staff:
        return leads if can_work_lead_flows(user) else []
    people = [(flow.slug, flow.name) for flow in active.for_people()]
    people.sort(key=lambda tab: tab[0] != INTAKE)
    return people + [(MINE, "My people"), (ALL, "Everyone")] + leads


def has_board(flow):
    """Flow tabs get a board; Intake (triage needs its form) and the mixed tabs don't"""
    return flow is not None and flow.slug != INTAKE


def initials(user):
    letters = (user.first_name[:1] + user.last_name[:1]) or user.email[:1]
    return letters.upper()


def open_enrollments():
    return Enrollment.objects.filter(ended_at__isnull=True)


def _last_activity(field):
    """The latest Activity's field for the enrollment's person or lead"""

    def latest(subject):
        return Subquery(
            Activity.objects.filter(**{subject: OuterRef(subject)}).order_by("-created_at").values(field)[:1]
        )

    return Coalesce(latest("person"), latest("lead"))


def row_queryset():
    """Enrollments with what a dashboard row shows (assignee groups for the Volunteer badge)"""
    return (
        Enrollment.objects.select_related("person__profile", "lead", "flow", "current_step__phase", "assignee")
        .prefetch_related("assignee__groups")
        .annotate(last_activity=_last_activity("created_at"))
    )


def decorate(rows, user):
    """Add what each row's controls need, in a fixed number of queries:
    step_choices (the flow's steps), can_leave (the user may move them off
    their current step), enroll_choices (active flows they could join; none
    for a lead) and ending_choices (the statuses it can end with, or switch to
    once ended).
    Boot Camp rows also get session (None means waitlist), session_choices and
    past_sessions."""
    rows = list(rows)
    steps_by_flow = defaultdict(list)
    for step in Step.objects.filter(phase__flow__in={row.flow_id for row in rows}).select_related("phase"):
        steps_by_flow[step.phase.flow_id].append(step)
    open_flows = defaultdict(dict)
    for person_id, flow_id, flow_name in open_enrollments().filter(
        person__in={row.person_id for row in rows}
    ).values_list("person_id", "flow_id", "flow__name"):
        open_flows[person_id][flow_id] = flow_name
    joinable = [flow for flow in Flow.objects.filter(active=True).for_people() if flow.slug != INTAKE]
    bootcamp.add_sessions(rows)
    for row in rows:
        row.step_choices = steps_by_flow[row.flow_id]
        row.can_leave = can_leave_step(user, row.current_step)
        row.ending_choices = ending_choices(row, steps=row.step_choices)
        if row.person_id is None:
            row.enroll_choices = row.also_in = []
            continue
        row.enroll_choices = [flow for flow in joinable if flow.pk not in open_flows[row.person_id]]
        row.also_in = [name for flow_id, name in open_flows[row.person_id].items() if flow_id != row.flow_id]
    return rows


def staff_users(flow=None):
    """Who can be assigned: active staff, and in a lead flow also active users
    with work_lead_flows (services.assign checks the same)"""
    who = Q(is_staff=True)
    if flow is not None and flow.subject == Flow.Subject.LEAD:
        who |= lead_workers_q()
    return (
        User.objects.filter(who, is_active=True)
        .distinct()
        .prefetch_related("groups")
        .order_by("first_name", "last_name", "email")
    )


def row(enrollment_pk, user):
    return decorate(row_queryset().filter(pk=enrollment_pk), user)[0]


def enrollments(user, tab, filters):
    """Enrollments for a tab, filtered by a valid DashboardFilters, ready to render"""
    return decorate(filtered(row_queryset(), user, tab, filters), user)


def filtered(qs, user, tab, filters):
    """qs narrowed to a tab and a valid DashboardFilters, in table order (by step, oldest in step first)"""
    if tab == MINE:
        qs = qs.filter(assignee=user, flow__subject=Flow.Subject.PERSON)
    elif tab == ALL:
        qs = qs.filter(flow__subject=Flow.Subject.PERSON)
    else:
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
                | Q(lead__first_name__icontains=word)
                | Q(lead__last_name__icontains=word)
                | Q(lead__org_name__icontains=word)
                | Q(lead__contact_email__icontains=word)
            )
    return qs.order_by(
        "flow__order", "current_step__phase__order", "current_step__phase_id",
        "current_step__order", "current_step_id", "step_entered_at", "pk",
    )


@dataclass
class Column:
    """One step on a board. cards are the first ones shown (or the page after
    offset); count is how many match the filters; open is everyone on the step,
    whatever the filters, so filtering doesn't collapse columns. left is how
    many come after cards, when cards moving since the board loaded make that
    differ from count less those shown."""

    step: Step
    cards: list
    count: int
    open: int
    offset: int = 0
    left: int = None

    @property
    def next_offset(self):
        return self.offset + len(self.cards)

    @property
    def more(self):
        return self.count - self.next_offset if self.left is None else self.left

    @property
    def cursor(self):
        """(step_entered_at, pk) of the last card shown; "Show more" pages after it"""
        last = self.cards[-1]
        return last.step_entered_at.isoformat(), last.pk

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
    reason = (
        Activity.objects.filter(enrollment=OuterRef("pk"), kind=Activity.Kind.STATUS_CHANGE)
        .order_by("-created_at")
        .values("text")[:1]
    )
    return row_queryset().filter(ended_at__isnull=True).annotate(
        last_activity_kind=_last_activity("kind"), status_reason=Subquery(reason)
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


def board_start(phases):
    """The step a phone-width board opens on: the first with cards, else the first"""
    columns = [column for group in phases for column in group.columns]
    busy = [column for column in columns if column.count]
    return (busy or columns)[0].step.pk if columns else None


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


def board_column(user, flow, step, filters, offset, after=None):
    """The page of a board column ("Show more") after the card at after,
    (step_entered_at, pk), else after offset. Paging after a card, not a count,
    doesn't skip one when a card shown earlier moves to another step. offset
    is still how many the board shows already, for "Showing N of M"."""
    qs = filtered(card_queryset(), user, flow.slug, filters).filter(current_step=step)
    if after is None:
        return Column(step, cards(qs[offset : offset + BOARD_PAGE], user), qs.count(), 0, offset)
    entered, pk = after
    rest = qs.filter(Q(step_entered_at__gt=entered) | Q(step_entered_at=entered, pk__gt=pk))
    page = cards(rest[:BOARD_PAGE], user)
    return Column(step, page, qs.count(), 0, offset, left=rest.count() - len(page))


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
    # People only, like the Everyone tab these link to
    totals = open_enrollments().filter(flow__subject=Flow.Subject.PERSON).aggregate(
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
