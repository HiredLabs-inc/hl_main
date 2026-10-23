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
from pipeline.models import Step
from userprofile.guards import app_permission_required

from . import services
from .conversation import conversation
from .forms import (
    AgentConfigForm,
    FollowUpForm,
    LeadFilterForm,
    LeadForm,
    LimitsForm,
    PartnersImportForm,
    ProviderConfigForm,
    RunForm,
)
from .models import AgentConfig, AgentLimits, AgentRun, Lead, ProviderConfig
from .tasks import run_agent_task

agents_required = app_permission_required("hlagents")


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _require(user, perm):
    if not user.has_perm(perm):
        raise PermissionDenied


@agents_required
def index_view(request):
    configs = AgentConfig.objects.filter(active=True).select_related("provider")
    for config in configs:
        config.last_run = config.runs.first()
        config.form = RunForm(initial={"request": config.default_request}, prefix=f"agent-{config.pk}")
        config.problem = services.start_problem(config)
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
    try:
        run = services.start_run(config, request.user, form.cleaned_data["request"])
    except ValidationError as e:
        messages.error(request, e.messages[0])
        return redirect("hlagents:index")
    return redirect("hlagents:run", run.pk)


def _run_context(request, run):
    context = {
        "run": run,
        "conversation": conversation(run.messages),
        "leads": services.attach_stages(run.leads.all()),
    }
    if not run.in_progress() and request.user.has_perm("hlagents.add_agentrun"):
        context["follow_up_problem"] = services.follow_up_problem(run)
        if not context["follow_up_problem"]:
            context["follow_up_form"] = FollowUpForm()
    return context


def _get_run(pk):
    return get_object_or_404(AgentRun.objects.select_related("config", "provider", "started_by"), pk=pk)


@agents_required
def run_view(request, pk):
    return render(request, "hlagents/run.html", _run_context(request, _get_run(pk)))


@agents_required
def run_status_view(request, pk):
    """The run body, polled while the run is queued or running"""
    return render(request, "hlagents/partials/run_body.html", _run_context(request, _get_run(pk)))


@agents_required
@require_POST
def follow_up_view(request, pk):
    _require(request.user, "hlagents.add_agentrun")
    run = _get_run(pk)
    form = FollowUpForm(request.POST)
    try:
        if not form.is_valid():
            raise ValidationError("The message can't be empty.")
        services.follow_up(run, form.cleaned_data["message"])
    except ValidationError as e:
        messages.error(request, e.messages[0])
    return redirect("hlagents:run", run.pk)


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
        if data["stage"]:
            leads = leads.filter(enrollments__ended_at__isnull=True, enrollments__current_step__title=data["stage"])
        if data["q"]:
            q = data["q"]
            leads = leads.filter(
                Q(org_name__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(contact_email__icontains=q)
            )
    page = Paginator(leads, 50).get_page(request.GET.get("page"))
    page.object_list = services.attach_stages(page.object_list)
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
    services.attach_stages([lead])
    context = {"lead": lead, "form": form, "timeline": timeline, "enrollment": lead.enrollment}
    return render(request, "hlagents/lead.html", context)


def _lead_row(request, lead, stage_error=""):
    services.attach_stages([lead])
    context = {"lead": lead, "show_run": request.POST.get("show_run"), "stage_error": stage_error}
    return render(request, "hlagents/partials/lead_row.html", context)


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
def stage_view(request, pk):
    _require(request.user, "hlagents.change_lead")
    lead = get_object_or_404(Lead, pk=pk)
    step = Step.objects.filter(pk=_int(request.POST.get("step"))).first()
    from_step = Step.objects.filter(pk=_int(request.POST.get("from_step"))).first()
    error = ""
    try:
        if step is None:
            raise ValidationError("Choose a stage.")
        services.set_stage(lead, step, request.user, from_step=from_step)
    except (ValidationError, PermissionDenied) as e:
        error = e.messages[0] if isinstance(e, ValidationError) else str(e)
    if request.headers.get("HX-Request"):
        # The row is redrawn either way, so it shows the stage that's saved
        return _lead_row(request, lead, stage_error=error)
    if error:
        messages.error(request, error)
    else:
        messages.success(request, f"Moved to {step.title}.")
    return redirect("hlagents:lead", lead.pk)


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


@agents_required
def settings_view(request):
    _require(request.user, "hlagents.change_agentconfig")
    limits = AgentLimits.get()
    can_change_limits = request.user.has_perm("hlagents.change_agentlimits")
    limits_form = LimitsForm(request.POST or None, instance=limits)
    if request.method == "POST":
        _require(request.user, "hlagents.change_agentlimits")
        if limits_form.is_valid():
            limits_form.save()
            messages.success(request, "Saved the caps and rates.")
            return redirect("hlagents:settings")
    providers = ProviderConfig.objects.all()
    for provider in providers:
        provider.problem = provider.key_problem()
    return render(
        request,
        "hlagents/settings.html",
        {
            "agents": AgentConfig.objects.select_related("provider"),
            "providers": providers,
            "limits": limits,
            "limits_form": limits_form if can_change_limits else None,
            "spent_today": AgentRun.spent_today(),
        },
    )


@agents_required
def agent_settings_view(request, pk=None):
    """Edit an agent, or add one (?copy=<pk> starts from a copy of another)."""
    if pk is None:
        _require(request.user, "hlagents.add_agentconfig")
        agent = AgentConfig()
        copy_pk = request.GET.get("copy", "")
        if copy_pk.isdigit():
            source = get_object_or_404(AgentConfig, pk=copy_pk)
            agent = AgentConfig(**{f: getattr(source, f) for f in AgentConfigForm.Meta.fields + ["tool_descriptions"]})
            agent.name = f"{source.name} (copy)"
    else:
        _require(request.user, "hlagents.change_agentconfig")
        agent = get_object_or_404(AgentConfig, pk=pk)
    form = AgentConfigForm(request.POST or None, instance=agent)
    if request.method == "POST" and form.is_valid():
        agent = form.save()
        messages.success(request, f"Saved {agent}. The next run uses these settings.")
        return redirect("hlagents:settings")
    return render(request, "hlagents/agent_settings.html", {"form": form, "agent": agent})


@agents_required
def provider_settings_view(request, pk=None):
    if pk is None:
        _require(request.user, "hlagents.add_providerconfig")
        provider = ProviderConfig()
    else:
        _require(request.user, "hlagents.change_providerconfig")
        provider = get_object_or_404(ProviderConfig, pk=pk)
    form = ProviderConfigForm(request.POST or None, instance=provider)
    if request.method == "POST" and form.is_valid():
        provider = form.save()
        messages.success(request, f"Saved {provider}.")
        return redirect("hlagents:settings")
    return render(request, "hlagents/provider_settings.html", {"form": form, "provider": provider})


@csrf_exempt
@require_POST
def task_run_agent(request):
    """Receive POST from Cloud Tasks"""
    if not is_authorized_task_request(request):
        return HttpResponse(status=403)
    task = work_task(request, run_agent_task)
    # A failed run is recorded on the run, not raised, so it isn't retried
    return JsonResponse({"status": task.status}, status=500 if task.has_failed() else 200)
