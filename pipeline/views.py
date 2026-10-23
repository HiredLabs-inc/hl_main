from django.db.models import Count, Prefetch, Q
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET

from userprofile.guards import staff_required

from . import dashboard
from .guards import can_work_flow, lead_flows_required
from .models import Flow, Phase, Step

VIEW_SESSION_KEY = "staff_dashboard_view"


def _query(params):
    """The dashboard's GET params, without the view and paging, for links that add their own"""
    params = params.copy()
    for key in ("view", "offset", "after", "after_pk", "part"):
        params.pop(key, None)
    return params.urlencode()


def _view(request, flow):
    """Table or board. A new session starts on the table; after that it opens
    on whichever was last chosen. Tabs without a board always show the table."""
    view = request.GET.get("view")
    if view in (dashboard.TABLE, dashboard.BOARD):
        request.session[VIEW_SESSION_KEY] = view
    else:
        view = request.session.get(VIEW_SESSION_KEY, dashboard.TABLE)
    return view if dashboard.has_board(flow) else dashboard.TABLE


@lead_flows_required
def dashboard_view(request):
    """Staff see every tab. Volunteers with work_lead_flows see only the lead
    flow tabs, without the header counts (they're about people)."""
    staff = request.user.is_staff
    tabs = dashboard.tabs(request.user)
    tab = request.GET.get("tab")
    if not tab:
        if not tabs:
            raise Http404
        tab = dashboard.INTAKE if staff else tabs[0][0]
        if not staff:
            return redirect(f"{request.path}?tab={tab}")
    if tab not in dict(tabs):
        if not staff and tab in dict(dashboard.tabs()):
            raise PermissionDenied
        raise Http404
    if request.GET.get("part") == "counts":
        if not staff:
            raise PermissionDenied
        return render(request, "pipeline/partials/count_strip.html", {"counts": dashboard.header_counts()})
    flow = Flow.objects.filter(slug=tab).first()
    view = _view(request, flow)
    # The filter form carries the view, so filtering and refreshes keep it
    params = request.GET.copy()
    params["view"] = view
    filters = dashboard.DashboardFilters(params, flow=flow)
    rows = phases = []
    if filters.is_valid():
        if view == dashboard.BOARD:
            phases = dashboard.board(request.user, flow, filters)
        else:
            rows = dashboard.enrollments(request.user, tab, filters)
    context = {
        "tabs": tabs,
        "tab": tab,
        "flow": flow,
        "view": view,
        "has_board": dashboard.has_board(flow),
        "view_choices": [(dashboard.TABLE, "Table"), (dashboard.BOARD, "Board")],
        "query": _query(request.GET),
        "filters": filters,
        "rows": rows,
        "phases": phases,
        "board_start": dashboard.board_start(phases),
        "results_template": f"pipeline/partials/{'board' if view == dashboard.BOARD else 'enrollment_table'}.html",
        "counts": dashboard.header_counts() if staff else None,
        "stale_days": dashboard.DEFAULT_STALE_DAYS,
        "staff_users": dashboard.staff_users(flow),
    }
    if request.headers.get("HX-Request"):
        return render(request, context["results_template"], context)
    return render(request, "pipeline/dashboard.html", context)


@require_GET
@lead_flows_required
def board_column_view(request, slug, step_pk):
    """The next cards of one board column ("Show more"), with the dashboard's filters"""
    flow = get_object_or_404(Flow, slug=slug, active=True)
    if not can_work_flow(request.user, flow):
        raise PermissionDenied
    if not dashboard.has_board(flow):
        raise Http404
    step = get_object_or_404(Step, pk=step_pk, phase__flow=flow)
    filters = dashboard.DashboardFilters(request.GET, flow=flow)
    try:
        offset = max(int(request.GET.get("offset", 0)), 0)
    except ValueError:
        offset = 0
    after = _after(request.GET)
    if not filters.is_valid():
        return render(request, "pipeline/partials/filter_errors.html", {"filters": filters}, status=400)
    column = dashboard.board_column(request.user, flow, step, filters, offset, after)
    context = {
        "flow": flow,
        "column": column,
        "stale_days": dashboard.DEFAULT_STALE_DAYS,
        "query": _query(request.GET),
    }
    return render(request, "pipeline/partials/board_cards.html", context)


def _after(params):
    """The last card a column shows, (step_entered_at, pk), from "Show more"; None if missing or bad"""
    try:
        entered = parse_datetime(params.get("after", ""))
        pk = int(params.get("after_pk", ""))
    except ValueError:
        return None
    return (entered, pk) if entered and entered.tzinfo else None


@staff_required
def flows_view(request):
    """What each flow's phases and steps are for, with how many people are on each step"""
    # Meta.ordering doesn't apply to GROUP BY queries, so order explicitly
    steps = Step.objects.annotate(open=Count("enrollments", filter=Q(enrollments__ended_at__isnull=True))).order_by(
        *Step._meta.ordering
    )
    phases = Phase.objects.prefetch_related(Prefetch("steps", queryset=steps))
    flows = Flow.objects.filter(active=True).prefetch_related(Prefetch("phases", queryset=phases))
    return render(request, "pipeline/flows.html", {"flows": flows})
