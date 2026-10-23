from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from background_tasks.queue import is_authorized_task_request, work_task
from userprofile.guards import app_permission_required

from . import services
from .conversation import conversation
from .forms import LeadFilterForm, LeadForm, PartnersImportForm, RunForm
from .models import AgentConfig, AgentRun, Lead
from .tasks import run_agent_task

agents_required = app_permission_required("hlagents")


def _require(user, perm):
    if not user.has_perm(perm):
        raise PermissionDenied


@agents_required
def index_view(request):
    configs = AgentConfig.objects.filter(active=True).select_related("provider")
    for config in configs:
        config.last_run = config.runs.first()
        config.form = RunForm(initial={"request": config.default_request}, prefix=f"agent-{config.pk}")
    runs = AgentRun.objects.select_related("config", "started_by").annotate(lead_count=Count("leads"))[:20]
    return render(request, "hlagents/index.html", {"configs": configs, "runs": runs})


@agents_required
@require_POST
def start_run_view(request, config_pk):
    _require(request.user, "hlagents.add_agentrun")
    config = get_object_or_404(AgentConfig, pk=config_pk, active=True)
    form = RunForm(request.POST, prefix=f"agent-{config.pk}")
    if not form.is_valid():
        messages.error(request, "The request can't be empty.")
        return redirect("hlagents:index")
    run = services.start_run(config, request.user, form.cleaned_data["request"])
    return redirect("hlagents:run", run.pk)


def _run_context(run):
    return {
        "run": run,
        "conversation": conversation(run.messages),
        "leads": run.leads.all(),
    }


@agents_required
def run_view(request, pk):
    run = get_object_or_404(AgentRun.objects.select_related("config", "provider", "started_by"), pk=pk)
    return render(request, "hlagents/run.html", _run_context(run))


@agents_required
def run_status_view(request, pk):
    """The run body, polled while the run is queued or running"""
    run = get_object_or_404(AgentRun.objects.select_related("config", "provider", "started_by"), pk=pk)
    return render(request, "hlagents/partials/run_body.html", _run_context(run))


@agents_required
def leads_view(request):
    filters = LeadFilterForm(request.GET or None)
    leads = Lead.objects.select_related("source_run__config")
    if filters.is_valid():
        data = filters.cleaned_data
        if data["kind"]:
            leads = leads.filter(kind=data["kind"])
        if data["review_status"]:
            leads = leads.filter(review_status=data["review_status"])
        if data["source"]:
            leads = leads.filter(source=data["source"])
        if data["q"]:
            q = data["q"]
            leads = leads.filter(
                Q(org_name__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(contact_email__icontains=q)
            )
    page = Paginator(leads, 50).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "hlagents/leads.html", {"filters": filters, "page": page, "query": query.urlencode()})


@agents_required
def lead_view(request, pk):
    lead = get_object_or_404(Lead.objects.select_related("source_run__config"), pk=pk)
    form = None
    if request.user.has_perm("hlagents.change_lead"):
        form = LeadForm(lead, request.POST if request.method == "POST" else None)
        if request.method == "POST" and form.is_valid():
            try:
                services.update_lead(lead, form.cleaned_data, request.user)
            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
            else:
                messages.success(request, "Saved.")
                return redirect("hlagents:lead", lead.pk)
            # The failed edit set attributes on lead; show what's saved
            lead.refresh_from_db()
    elif request.method == "POST":
        raise PermissionDenied
    timeline = lead.activities.select_related("actor")
    return render(request, "hlagents/lead.html", {"lead": lead, "form": form, "timeline": timeline})


def _lead_row(request, lead):
    return render(request, "hlagents/partials/lead_row.html", {"lead": lead, "show_run": request.POST.get("show_run")})


@agents_required
@require_POST
def review_view(request, pk):
    _require(request.user, "hlagents.change_lead")
    lead = get_object_or_404(Lead, pk=pk)
    try:
        services.review(lead, request.POST.get("status", ""), request.user)
    except ValidationError as e:
        return HttpResponse(e.messages[0], status=400)
    return _lead_row(request, lead)


@agents_required
@require_POST
def opt_out_view(request, pk):
    _require(request.user, "hlagents.change_lead")
    lead = get_object_or_404(Lead, pk=pk)
    services.set_opted_out(lead, request.POST.get("opted_out") == "1", request.user)
    if request.headers.get("HX-Request"):
        return _lead_row(request, lead)
    return redirect("hlagents:lead", lead.pk)


@agents_required
def import_view(request):
    _require(request.user, "hlagents.add_lead")
    form = PartnersImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            partners = services.read_partners_csv(form.cleaned_data["file"])
        except ValidationError as e:
            for error in e.messages:
                form.add_error("file", error)
        else:
            counts = services.import_partners(partners, request.user)
            messages.success(
                request,
                f"Imported {len(partners)} partners: {counts['created']} new, {counts['updated']} updated, "
                f"{counts['unchanged']} unchanged.",
            )
            return redirect(f"{reverse('hlagents:leads')}?kind=outreach&source=import")
    return render(request, "hlagents/import.html", {"form": form})


@csrf_exempt
@require_POST
def task_run_agent(request):
    """Receive POST from Cloud Tasks"""
    if not is_authorized_task_request(request):
        return HttpResponse(status=403)
    task = work_task(request, run_agent_task)
    # A failed run is recorded on the run, not raised, so it isn't retried
    return JsonResponse({"status": task.status}, status=500 if task.has_failed() else 200)
