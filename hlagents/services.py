"""Creating runs and saving what they find."""
from django.db import IntegrityError, transaction

from hlagents.models import AgentConfig, AgentRun, Lead


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
                Lead.objects.create(kind=agent.lead_kind, dedupe_key=key, source_run=run, **values)
        except IntegrityError:
            # Another run saved it first
            skipped += 1
            continue
        inserted += 1
    return inserted, skipped
