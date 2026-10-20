from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import render

from userprofile.guards import staff_required

from . import dashboard
from .models import Flow, Phase, Step


@staff_required
def dashboard_view(request):
    tabs = dashboard.tabs()
    tab = request.GET.get("tab") or dashboard.INTAKE
    if tab not in dict(tabs):
        raise Http404
    flow = Flow.objects.filter(slug=tab).first()
    filters = dashboard.DashboardFilters(request.GET, flow=flow)
    rows = dashboard.enrollments(request.user, tab, filters) if filters.is_valid() else []
    context = {
        "tabs": tabs,
        "tab": tab,
        "flow": flow,
        "filters": filters,
        "rows": rows,
        "counts": dashboard.header_counts(),
        "stale_days": dashboard.DEFAULT_STALE_DAYS,
    }
    if request.headers.get("HX-Request"):
        return render(request, "pipeline/partials/enrollment_table.html", context)
    return render(request, "pipeline/dashboard.html", context)


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
