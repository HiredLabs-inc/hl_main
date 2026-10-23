"""AI agents staff can run from /agents/ (docs/hlagents.md §3.2).

Providers and agents are configured in the DB so staff can switch model or
provider without a deploy. Agent types (how a reply is parsed into leads) are
code, in hlagents.agents.
"""
import os
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from hl_main.models import TrackedModel
from hlagents.agents import agent_type_choices, get_agent_type

User = settings.AUTH_USER_MODEL


class ProviderConfig(TrackedModel):
    class Kind(models.TextChoices):
        OLLAMA = "ollama", "Ollama"

    name = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    base_url = models.URLField(blank=True)
    # Name of the env var (loaded from Secret Manager on Cloud Run) that holds the
    # API key. Keys are never stored in the DB.
    secret_env = models.CharField(max_length=100, blank=True)
    # Admin-entered estimates for the cost cap, in $ per million tokens
    input_cost_per_mtok = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    output_cost_per_mtok = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def api_key(self):
        if self.secret_env not in settings.HLAGENTS_PROVIDER_SECRETS:
            return ""
        return os.environ.get(self.secret_env, "")

    def key_problem(self):
        """Why the provider's key can't be used, or "" if it can (or none is needed)."""
        if not self.secret_env:
            return ""
        if self.secret_env not in settings.HLAGENTS_PROVIDER_SECRETS:
            return f"{self.secret_env} isn't in HLAGENTS_PROVIDER_SECRETS, so {self} can't be used."
        if not self.api_key():
            return f"{self.secret_env} isn't set, so {self} can't be used."
        return ""

    def token_cost(self, input_tokens, output_tokens):
        return (
            self.input_cost_per_mtok * input_tokens + self.output_cost_per_mtok * output_tokens
        ) / Decimal(1_000_000)


class AgentConfig(TrackedModel):
    name = models.CharField(max_length=100, unique=True)
    agent_type = models.CharField(max_length=50, choices=agent_type_choices())
    provider = models.ForeignKey(ProviderConfig, on_delete=models.PROTECT, related_name="agents")
    model = models.CharField(max_length=100)
    system_prompt = models.TextField()
    default_request = models.TextField()
    tools = models.JSONField(default=list, blank=True)
    # Per-tool description overrides, {tool name: description}
    tool_descriptions = models.JSONField(default=dict, blank=True)
    max_iterations = models.PositiveSmallIntegerField(default=15)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def agent(self):
        return get_agent_type(self.agent_type)


class AgentRun(TrackedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"
        CAPPED = "capped", "Stopped at cost cap"

    config = models.ForeignKey(AgentConfig, on_delete=models.PROTECT, related_name="runs")
    # What the run actually used; follow-ups keep using it even if the config
    # changes. The system prompt is the first message.
    provider = models.ForeignKey(ProviderConfig, on_delete=models.PROTECT, related_name="runs")
    model = models.CharField(max_length=100)
    started_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    messages = models.JSONField(default=list)
    result = models.TextField(blank=True)
    error = models.TextField(blank=True)
    iterations = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    tool_calls = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    task = models.ForeignKey(
        "background_tasks.Task", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.config} run {self.pk}"

    def in_progress(self):
        return self.status in (self.Status.QUEUED, self.Status.RUNNING)

    @classmethod
    def spent_today(cls, exclude=None):
        runs = cls.objects.filter(created_at__date=timezone.localdate())
        if exclude is not None:
            runs = runs.exclude(pk=exclude.pk)
        return runs.aggregate(total=Sum("cost"))["total"] or Decimal(0)


class Lead(TrackedModel):
    class Kind(models.TextChoices):
        FUNDING = "funding", "Funding"
        OUTREACH = "outreach", "Outreach"

    class Source(models.TextChoices):
        AGENT = "agent", "Agent"
        IMPORT = "import", "Imported"

    class ReviewStatus(models.TextChoices):
        NEW = "new", "New"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.AGENT)
    # Normalized org name (funding) or email (outreach); see hlagents.agents
    dedupe_key = models.CharField(max_length=255)
    org_name = models.CharField(max_length=255, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    # Text, because models return ranges and phrases like "rolling"
    funding_amount = models.CharField(max_length=100, blank=True)
    application_deadline = models.CharField(max_length=100, blank=True)
    url = models.URLField(max_length=500, blank=True)
    justification = models.TextField(blank=True)
    review_status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.NEW)
    # From the community partners CSV's Status column ("Bounced #3" is 3)
    bounces = models.PositiveSmallIntegerField(default=0)
    # Only a mark on the record; the opt-out itself is handled in the email
    opted_out_at = models.DateTimeField(null=True, blank=True)
    source_run = models.ForeignKey(
        AgentRun, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["kind", "dedupe_key"], name="hlagents_lead_unique_per_kind"),
        ]

    def __str__(self):
        name = " ".join(n for n in (self.first_name, self.last_name) if n)
        return f"{name} ({self.org_name})" if name else self.org_name


class AgentLimits(models.Model):
    """One row (pk=1) of admin-adjustable cost caps (docs/hlagents.md §3.8)."""

    run_cost_cap = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    daily_cost_cap = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("10.00"))
    # $ per call, {tool name: "0.008"}
    tool_costs = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "agent limits"

    def __str__(self):
        return "Agent limits"

    @classmethod
    def get(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def tool_cost(self, name):
        return Decimal(str(self.tool_costs.get(name, 0)))
