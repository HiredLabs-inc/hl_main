"""The only code that changes runs and leads. Every change to a lead is recorded
on its pipeline Activity timeline (docs/hlagents.md §3.10)."""
import csv
import io
import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from background_tasks.queue import queue_task
from hlagents.agents import agent_for_lead_kind
from hlagents.models import AgentConfig, AgentLimits, AgentRun, Lead
from pipeline.models import Activity

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


def create_run(config: AgentConfig, started_by, request: str = "") -> AgentRun:
    """A queued run of the config, starting from its prompt and default request."""
    return AgentRun.objects.create(
        config=config,
        provider=config.provider,
        model=config.model,
        started_by=started_by,
        messages=[
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": request or config.default_request},
        ],
    )


def _cap_problem(run=None):
    """Why no run can start, or this run can't continue, under the cost caps; or ""."""
    limits = AgentLimits.get()
    if AgentRun.spent_today() >= limits.daily_cost_cap:
        return f"Today's runs have reached the ${limits.daily_cost_cap} daily cap."
    if run is not None and run.cost >= limits.run_cost_cap:
        return f"This run has reached the ${limits.run_cost_cap} run cap."
    return ""


def _provider_problem(provider):
    if not provider.active:
        return f"{provider} is turned off in settings."
    return provider.key_problem()


def start_problem(config: AgentConfig) -> str:
    """Why the config can't start a run right now, or ""."""
    return _provider_problem(config.provider) or _cap_problem()


def follow_up_problem(run: AgentRun) -> str:
    """Why the run can't take a follow-up right now, or ""."""
    if run.in_progress():
        return "The agent is still working on this run."
    return _provider_problem(run.provider) or _cap_problem(run)


def _queue(run):
    run.task = queue_task(reverse("hlagents:task_run_agent"), {"run_id": run.pk})
    run.save(update_fields=["task", "updated_at"])


def start_run(config: AgentConfig, started_by, request: str = "") -> AgentRun:
    """Create a run and queue it for the worker. Raises ValidationError if it
    can't start (start_problem)."""
    if problem := start_problem(config):
        raise ValidationError(problem)
    run = create_run(config, started_by, request)
    _queue(run)
    return run


def follow_up(run: AgentRun, text: str) -> AgentRun:
    """Add a message to a finished run and queue it again. New candidates are
    added to the same run (docs/hlagents.md §3.3). Raises ValidationError if
    the run can't continue (follow_up_problem)."""
    text = (text or "").strip()
    if not text:
        raise ValidationError("The message can't be empty.")
    with transaction.atomic():
        run = AgentRun.objects.select_for_update().select_related("provider").get(pk=run.pk)
        if problem := follow_up_problem(run):
            raise ValidationError(problem)
        run.messages.append({"role": "user", "content": text})
        run.status = AgentRun.Status.QUEUED
        run.result = run.error = ""
        run.save()
    _queue(run)
    return run


def _fit(field_name, value):
    max_length = Lead._meta.get_field(field_name).max_length
    return value[:max_length] if max_length else value


def save_leads(run: AgentRun, candidates) -> tuple[int, int]:
    """Create a lead per new candidate. Returns (inserted, skipped): candidates
    without a dedupe key, or already a lead of this kind, are skipped."""
    agent = run.config.agent()
    inserted = skipped = 0
    for candidate in candidates:
        key = _fit("dedupe_key", agent.dedupe_key(candidate))
        if not key or Lead.objects.filter(kind=agent.lead_kind, dedupe_key=key).exists():
            skipped += 1
            continue
        values = {field: _fit(field, value) for field, value in agent.to_lead(candidate).items()}
        try:
            with transaction.atomic():
                lead = Lead.objects.create(kind=agent.lead_kind, dedupe_key=key, source_run=run, **values)
                _record(lead, run.started_by, Activity.Kind.LEAD_FOUND, text=f"{run.config.name}, run {run.pk}")
        except IntegrityError:
            # Another run saved it first
            skipped += 1
            continue
        inserted += 1
    return inserted, skipped


@transaction.atomic
def review(lead: Lead, status, actor) -> Lead:
    """Approve or reject a lead, or set it back to new."""
    if status not in Lead.ReviewStatus.values:
        raise ValidationError(f"{status} isn't a review status.")
    if status != lead.review_status:
        old = lead.get_review_status_display()
        lead.review_status = status
        lead.save(update_fields=["review_status", "updated_at"])
        _record(lead, actor, Activity.Kind.REVIEW, from_value=old, to_value=lead.get_review_status_display())
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
    columns, docs/hlagents.md §3.9). Raises ValidationError listing every bad
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
    """Create or update an approved Outreach lead per partner email. Returns
    counts of created, updated and unchanged leads."""
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
        counts["updated" if changed else "unchanged"] += 1
    return counts
