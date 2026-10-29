"""The only code that changes runs and leads. Every change to a lead is recorded
on its pipeline Activity timeline (docs/designs/completed/hlagents.md §3.10)."""
import csv
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from background_tasks.queue import queue_task
from hlagents.agents import CORRECTABLE, DUPLICATE, INCOMPLETE, agent_for_lead_kind
from hlagents.conversation import note, tool_text
from hlagents.models import AgentConfig, AgentLimits, AgentRun, Lead, ProviderConfig, spent_today
from pipeline import services as pipeline
from pipeline.models import Activity, Enrollment, Flow, Step

# The pipeline flow each kind of lead joins when approved (docs/designs/completed/hlagents.md §3.6)
FLOW_SLUGS = {Lead.Kind.FUNDING: "funding", Lead.Kind.OUTREACH: "outreach"}
# Where community partners go in the Outreach flow
PARTNER_STEP = "Partner"

# Fields staff can edit, per lead kind
EDITABLE_FIELDS = {
    Lead.Kind.FUNDING: ["org_name", "funding_amount", "application_deadline", "url", "justification"],
    Lead.Kind.OUTREACH: ["first_name", "last_name", "org_name", "contact_email", "justification"],
}
FIELD_LABELS = {
    "org_name": "Organization",
    "contact_email": "Email",
    "funding_amount": "Amount",
    "application_deadline": "Deadline",
    "url": "URL",
    "justification": "Why it fits",
}


def field_label(field):
    return FIELD_LABELS.get(field) or Lead._meta.get_field(field).verbose_name.capitalize()


def _record(lead, actor, kind, text="", from_value="", to_value=""):
    return Activity.objects.create(
        lead=lead, kind=kind, text=text, from_value=from_value[:200], to_value=to_value[:200], actor=actor
    )


# How many known leads an agent is told about, most recent first
KNOWN_LEADS_LIMIT = 300
STOPPED_BY_STAFF = "Stopped by staff."
WORKER_DIED = "The worker stopped before the run finished."


def known_leads_hint(kind) -> str:
    """A note listing the leads of this kind we already have, so the agent
    doesn't spend its searches finding them again; or "" if there are none."""
    leads = Lead.objects.filter(kind=kind).order_by("-created_at")[:KNOWN_LEADS_LIMIT]
    if kind == Lead.Kind.OUTREACH:
        lines = []
        for lead in leads:
            name = " ".join(part for part in (lead.first_name, lead.last_name) if part)
            about = ", ".join(part for part in (name, lead.org_name) if part)
            lines.append(f"- {lead.contact_email}" + (f" ({about})" if about else ""))
        what = "people"
    else:
        lines = [f"- {name}" for name in dict.fromkeys(lead.org_name for lead in leads if lead.org_name)]
        what = "funders"
    if not lines:
        return ""
    return f"We already know these {what}. Don't return them again:\n" + "\n".join(lines)


def _with_known_leads(messages, kind):
    if hint := known_leads_hint(kind):
        messages.append(note(hint, "Already known"))
    return messages


def create_run(config: AgentConfig, started_by, request: str = "", provider=None, model=None) -> AgentRun:
    """A queued run of the config, starting from its prompt and default request,
    with today's date and the leads we already have. It runs on the config's
    provider and model unless others are given."""
    today = timezone.localdate().strftime("%B %-d, %Y")
    return AgentRun.objects.create(
        config=config,
        provider=provider or config.provider,
        model=model or config.model,
        started_by=started_by,
        messages=_with_known_leads(
            [
                {"role": "system", "content": f"{config.system_prompt}\n\nToday is {today}."},
                {"role": "user", "content": request or config.default_request},
            ],
            config.agent().lead_kind,
        ),
    )


def cap_problem(run=None):
    """Why no run can start, or this run can't continue, under the cost caps; or ""."""
    limits = AgentLimits.get()
    if spent_today() >= limits.daily_cost_cap:
        return f"Today's agent runs and tasks have reached the ${limits.daily_cost_cap} daily cap."
    if run is not None and run.cost >= limits.run_cost_cap:
        return f"This run has reached the ${limits.run_cost_cap} run cap."
    return ""


def provider_problem(provider):
    if not provider.active:
        return f"{provider} is turned off in settings."
    return provider.key_problem()


def run_choices(config: AgentConfig) -> list[tuple[ProviderConfig, str]]:
    """The (provider, model) pairs a run of the config can use: its own first,
    then the models staff listed on each provider. Providers that can't be used
    right now are left out."""
    providers = [config.provider] + [p for p in ProviderConfig.objects.filter(active=True) if p.pk != config.provider_id]
    choices = []
    for provider in providers:
        if provider_problem(provider):
            continue
        models = [config.model] if provider == config.provider else []
        choices += [(provider, model) for model in dict.fromkeys(models + provider.models)]
    return choices


def start_problem(config: AgentConfig, choices=None) -> str:
    """Why the config can't start a run right now, or "". Pass run_choices(config)
    if you have it."""
    if problem := cap_problem():
        return problem
    if not (run_choices(config) if choices is None else choices):
        return provider_problem(config.provider) or "No provider can run this agent right now."
    return ""


def follow_up_problem(run: AgentRun) -> str:
    """Why the run can't take a follow-up right now, or ""."""
    if run.in_progress():
        return "The agent is still working on this run."
    return provider_problem(run.provider) or cap_problem(run)


def _queue(run):
    run.task = queue_task(reverse("hlagents:task_run_agent"), {"run_id": run.pk})
    run.save(update_fields=["task", "updated_at"])


def start_run(config: AgentConfig, started_by, request: str = "", provider=None, model=None) -> AgentRun:
    """Create a run and queue it for the worker, on the config's provider and
    model or one of its other run_choices. Raises ValidationError if it can't
    start (start_problem), or the choice isn't one of them."""
    if problem := cap_problem():
        raise ValidationError(problem)
    if provider is None and model is None:
        if problem := provider_problem(config.provider):
            raise ValidationError(problem)
    elif (provider, model) not in run_choices(config):
        raise ValidationError("That model isn't available. Pick another.")
    run = create_run(config, started_by, request, provider, model)
    _queue(run)
    return run


def follow_up(run: AgentRun, text: str) -> AgentRun:
    """Add a message to a finished run and queue it again. New candidates are
    added to the same run (docs/designs/completed/hlagents.md §3.3). Raises ValidationError if
    the run can't continue (follow_up_problem)."""
    text = (text or "").strip()
    if not text:
        raise ValidationError("The message can't be empty.")
    with transaction.atomic():
        run = AgentRun.objects.select_for_update().select_related("provider").get(pk=run.pk)
        if problem := follow_up_problem(run):
            raise ValidationError(problem)
        run.messages.append({"role": "user", "content": text})
        _with_known_leads(run.messages, run.config.agent().lead_kind)
        run.status = AgentRun.Status.QUEUED
        run.result = run.error = ""
        run.stop_requested = False
        run.save()
    _queue(run)
    return run


def stop_run(run: AgentRun) -> AgentRun:
    """Stop a queued run now. A running one is asked to stop, and does before its
    next step or tool call (docs/designs/in-progress/gcp-agents.md §3.7)."""
    with transaction.atomic():
        run = AgentRun.objects.select_for_update().get(pk=run.pk)
        if run.status == AgentRun.Status.QUEUED:
            # The worker only starts queued runs, so it skips this one
            run.status = AgentRun.Status.STOPPED
            run.error = STOPPED_BY_STAFF
            run.save(update_fields=["status", "error", "updated_at"])
        elif run.status == AgentRun.Status.RUNNING:
            run.stop_requested = True
            run.save(update_fields=["stop_requested", "updated_at"])
    return run


def fail_stale_runs() -> int:
    """Mark Failed the runs whose worker was killed mid-run, which nothing else
    would: still Running, but not saved for longer than the worker's timeout.
    The loop saves after every step, so a live run is never this old."""
    now = timezone.now()
    cutoff = now - timedelta(seconds=settings.HLAGENTS_STALE_RUN_AFTER)
    return AgentRun.objects.filter(status=AgentRun.Status.RUNNING, updated_at__lt=cutoff).update(
        status=AgentRun.Status.FAILED, error=WORKER_DIED, stop_requested=False, updated_at=now
    )


def _fit(field_name, value):
    max_length = Lead._meta.get_field(field_name).max_length
    return value[:max_length] if max_length else value


@dataclass
class SaveResult:
    inserted: int = 0
    # {reason: count} of candidates that weren't saved
    skipped: Counter = field(default_factory=Counter)
    # [(candidate, reason)] the agent could fix (agents.CORRECTABLE)
    rejected: list = field(default_factory=list)

    def add(self, other: "SaveResult"):
        self.inserted += other.inserted
        self.skipped += other.skipped
        self.rejected += other.rejected

    def summary(self) -> str:
        text = f"Inserted {self.inserted}."
        if self.skipped:
            text += " Skipped: " + ", ".join(f"{count} {reason}" for reason, count in self.skipped.most_common()) + "."
        return text


def save_leads(run: AgentRun, candidates) -> SaveResult:
    """Create a lead per new, valid candidate. Candidates without a dedupe key,
    already a lead of this kind, or failing the agent's checks against what its
    tools returned (AgentType.validate) are skipped, and counted by reason."""
    agent = run.config.agent()
    sources = tool_text(run.messages)
    result = SaveResult()
    for candidate in candidates:
        key = _fit("dedupe_key", agent.dedupe_key(candidate))
        if not key:
            reason = INCOMPLETE
        elif Lead.objects.filter(kind=agent.lead_kind, dedupe_key=key).exists():
            reason = DUPLICATE
        else:
            reason = agent.validate(candidate, sources)
        if not reason:
            values = {field: _fit(field, value) for field, value in agent.to_lead(candidate).items()}
            try:
                with transaction.atomic():
                    lead = Lead.objects.create(kind=agent.lead_kind, dedupe_key=key, source_run=run, **values)
                    _record(lead, run.started_by, Activity.Kind.LEAD_FOUND, text=f"{run.config.name}, run {run.pk}")
            except IntegrityError:
                # Another run saved it first
                reason = DUPLICATE
        if reason:
            result.skipped[reason] += 1
            if reason in CORRECTABLE:
                result.rejected.append((candidate, reason))
        else:
            result.inserted += 1
    return result


def open_enrollment(lead: Lead):
    return Enrollment.objects.filter(lead=lead, ended_at__isnull=True).select_related("flow", "current_step").first()


def attach_stages(leads) -> list:
    """Set lead.enrollment (open, or None) and lead.stage_steps (its flow's
    steps, in board order) on each lead, in two queries plus one per flow"""
    leads = list(leads)
    enrollments = Enrollment.objects.filter(lead__in=leads, ended_at__isnull=True).select_related("flow", "current_step")
    by_lead = {e.lead_id: e for e in enrollments}
    steps = {}
    for lead in leads:
        lead.enrollment = by_lead.get(lead.pk)
        lead.stage_steps = []
        if lead.enrollment:
            flow_id = lead.enrollment.flow_id
            if flow_id not in steps:
                steps[flow_id] = list(Step.objects.filter(phase__flow_id=flow_id).select_related("phase"))
            lead.stage_steps = steps[flow_id]
    return leads


def stage_choices():
    """Step titles of the lead flows, grouped by flow, for filtering leads by stage"""
    choices = {}
    steps = Step.objects.filter(phase__flow__slug__in=FLOW_SLUGS.values()).select_related("phase__flow")
    for step in steps:
        choices.setdefault(step.phase.flow.name, []).append((step.title, step.title))
    return list(choices.items())


def set_stage(lead: Lead, step: Step, actor, from_step: Step = None) -> Enrollment:
    """Move the lead's open enrollment to step. With from_step, refuse
    (StaleStep) unless it's still there, e.g. after a move on the board."""
    enrollment = open_enrollment(lead)
    if enrollment is None:
        raise ValidationError("Approve this lead to track its stage.")
    return pipeline.move_to_step(enrollment, step, actor, from_step=from_step)


def _place(lead: Lead, actor, step_title=None) -> bool:
    """Enroll the lead in its kind's flow if it isn't already, at step_title
    (default: the first step). An enrollment on another step is moved there
    only when step_title is given. Returns whether anything changed; nothing
    does if the flow is missing or inactive."""
    flow = Flow.objects.filter(slug=FLOW_SLUGS[lead.kind], active=True).first()
    if flow is None:
        return False
    step = Step.objects.filter(phase__flow=flow, title=step_title).first() if step_title else None
    enrollment = open_enrollment(lead)
    if enrollment is None:
        pipeline.enroll(None, flow, actor, step=step, lead=lead)
        return True
    if step is not None and enrollment.current_step_id != step.pk:
        pipeline.move_to_step(enrollment, step, actor)
        return True
    return False


@transaction.atomic
def review(lead: Lead, status, actor) -> Lead:
    """Approve or reject a lead, or set it back to new. Approving enrolls it in
    its flow (imported partners at Partner); rejecting withdraws it."""
    if status not in Lead.ReviewStatus.values:
        raise ValidationError(f"{status} isn't a review status.")
    if status == lead.review_status:
        return lead
    old = lead.get_review_status_display()
    lead.review_status = status
    lead.save(update_fields=["review_status", "updated_at"])
    _record(lead, actor, Activity.Kind.REVIEW, from_value=old, to_value=lead.get_review_status_display())
    if status == Lead.ReviewStatus.APPROVED:
        _place(lead, actor, PARTNER_STEP if lead.source == Lead.Source.IMPORT else None)
    elif status == Lead.ReviewStatus.REJECTED and (enrollment := open_enrollment(lead)):
        pipeline.set_status(enrollment, Enrollment.Status.WITHDRAWN, actor, reason="Lead rejected")
    return lead


@transaction.atomic
def update_lead(lead: Lead, values: dict, actor) -> Lead:
    """Save edited fields and re-key the lead. Raises ValidationError if the
    edit makes it a duplicate or removes what it's keyed on."""
    changes = []
    for field in EDITABLE_FIELDS[lead.kind]:
        new = (values.get(field) or "").strip()
        old = getattr(lead, field)
        if new != old:
            changes.append(f"{field_label(field)}: {old or '(blank)'} → {new or '(blank)'}")
            setattr(lead, field, new)
    if not changes:
        return lead

    key_field = "contact_email" if lead.kind == Lead.Kind.OUTREACH else "org_name"
    key = agent_for_lead_kind(lead.kind).dedupe_key({key_field: getattr(lead, key_field)})
    if not key:
        raise ValidationError({key_field: "This is needed to tell leads apart."})
    if Lead.objects.filter(kind=lead.kind, dedupe_key=key).exclude(pk=lead.pk).exists():
        raise ValidationError({key_field: "Another lead already has this."})
    if lead.kind == Lead.Kind.OUTREACH:
        lead.contact_email = key
    lead.dedupe_key = key
    lead.save()
    _record(lead, actor, Activity.Kind.LEAD_EDITED, text="\n".join(changes))
    return lead


@transaction.atomic
def set_opted_out(lead: Lead, opted_out: bool, actor) -> Lead:
    """Mark or unmark a lead as opted out. Only a mark: the opt-out itself is
    handled in the email."""
    if opted_out == (lead.opted_out_at is not None):
        return lead
    lead.opted_out_at = timezone.now() if opted_out else None
    lead.save(update_fields=["opted_out_at", "updated_at"])
    _record(lead, actor, Activity.Kind.OPT_OUT, to_value="Opted out" if opted_out else "Opt-out removed")
    return lead


BOUNCED = re.compile(r"^bounced\s*(?:#\s*(\d+))?$", re.IGNORECASE)


def _bounces(status):
    """0 for a blank Status, 1 for "Bounced", N for "Bounced #N"; None if unknown."""
    status = (status or "").strip()
    if not status:
        return 0
    match = BOUNCED.match(status)
    if not match:
        return None
    return int(match.group(1) or 1)


def read_partners_csv(file) -> dict[str, int]:
    """{email: bounces} from a community partners CSV (EMAIL and Status
    columns, docs/designs/completed/hlagents.md §3.9). Raises ValidationError listing every bad
    row, so nothing is imported from a file with problems."""
    try:
        text = file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationError("The file isn't a UTF-8 CSV.")
    reader = csv.DictReader(io.StringIO(text))
    headers = {(h or "").strip().lower(): h for h in reader.fieldnames or []}
    if "email" not in headers:
        raise ValidationError("The file needs an EMAIL column.")

    agent = agent_for_lead_kind(Lead.Kind.OUTREACH)
    partners, errors = {}, []
    for line, row in enumerate(reader, start=2):
        raw_email = (row.get(headers["email"]) or "").strip()
        status = row.get(headers["status"], "") if "status" in headers else ""
        if not raw_email and not (status or "").strip():
            continue
        email = agent.dedupe_key({"contact_email": raw_email})
        bounces = _bounces(status)
        if not email:
            errors.append(f"Row {line}: {raw_email or '(blank)'} isn't an email address.")
        elif bounces is None:
            errors.append(f"Row {line}: unknown Status {status.strip()!r}.")
        else:
            partners[email] = max(bounces, partners.get(email, 0))
    if errors:
        raise ValidationError(errors)
    return partners


@transaction.atomic
def import_partners(partners: dict[str, int], actor) -> dict[str, int]:
    """Create or update an approved Outreach lead per partner email, on the
    Outreach flow's Partner step. Returns counts of created, updated and
    unchanged leads."""
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    existing = {lead.dedupe_key: lead for lead in Lead.objects.filter(kind=Lead.Kind.OUTREACH, dedupe_key__in=partners)}
    for email, bounces in partners.items():
        lead = existing.get(email)
        if lead is None:
            lead = Lead.objects.create(
                kind=Lead.Kind.OUTREACH,
                source=Lead.Source.IMPORT,
                dedupe_key=email,
                contact_email=email,
                review_status=Lead.ReviewStatus.APPROVED,
                bounces=bounces,
            )
            _record(lead, actor, Activity.Kind.LEAD_IMPORTED, text="Community partners CSV")
            _place(lead, actor, PARTNER_STEP)
            counts["created"] += 1
            continue

        changed = False
        if lead.bounces != bounces:
            _record(lead, actor, Activity.Kind.LEAD_EDITED, text=f"Bounces: {lead.bounces} → {bounces} (partners CSV)")
            lead.bounces = bounces
            lead.save(update_fields=["bounces", "updated_at"])
            changed = True
        if lead.review_status != Lead.ReviewStatus.APPROVED:
            review(lead, Lead.ReviewStatus.APPROVED, actor)
            changed = True
        changed = _place(lead, actor, PARTNER_STEP) or changed
        counts["updated" if changed else "unchanged"] += 1
    return counts
