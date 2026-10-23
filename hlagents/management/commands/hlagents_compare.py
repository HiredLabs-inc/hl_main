"""Compare models on one agent (docs/hlagents.md §8, H7).

Each run starts from the same leads: by default it's rolled back afterwards, so
one model's leads don't count as "already known" for the next. Pass --keep to
keep the runs and review their leads in /agents/runs/.

    python manage.py hlagents_compare --agent "Funding opportunities" \\
        --models gemma4:31b,gpt-oss:120b --request "Find 5 ..." --repeat 2
"""
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hlagents import services
from hlagents.loop import run_agent
from hlagents.models import AgentConfig


class Rollback(Exception):
    pass


class Command(BaseCommand):
    help = "Run one agent with several models and print what each found."

    def add_arguments(self, parser):
        parser.add_argument("--agent", required=True, help="The agent's name or id")
        parser.add_argument("--models", required=True, help="Comma-separated model names")
        parser.add_argument("--request", default="", help="The request (default: the agent's default request)")
        parser.add_argument("--repeat", type=int, default=1, help="Runs per model")
        parser.add_argument("--steps", type=int, help="Step limit per turn (default: the agent's)")
        parser.add_argument("--keep", action="store_true", help="Keep the runs and their leads")

    def handle(self, *args, **options):
        agent = options["agent"]
        config = AgentConfig.objects.filter(**({"pk": agent} if agent.isdigit() else {"name": agent})).first()
        if config is None:
            raise CommandError(f"No agent named {agent}.")
        models = [m.strip() for m in options["models"].split(",") if m.strip()]
        if options["steps"]:
            # Not saved: the loop reads the limit from run.config
            config.max_iterations = options["steps"]

        rows = []
        for model in models:
            for _ in range(options["repeat"]):
                self.stdout.write(f"\n== {model}")
                rows.append(self._run(config, model, options["request"], options["keep"]))

        self.stdout.write("\nmodel | status | steps | tool calls | tokens | seconds | result")
        for row in rows:
            self.stdout.write(" | ".join(str(value) for value in row))

    def _run(self, config, model, request, keep):
        try:
            with transaction.atomic():
                run = services.create_run(config, None, request)
                run.config = config
                run.model = model
                run.save(update_fields=["model"])
                started = time.monotonic()
                run_agent(run)
                seconds = round(time.monotonic() - started)
                for lead in run.leads.order_by("pk"):
                    self.stdout.write(f"  {lead} | {lead.contact_email or lead.url} | {lead.funding_amount} | "
                                      f"{lead.application_deadline} | {lead.justification}")
                if run.error:
                    self.stdout.write(f"  error: {run.error}")
                row = (model, run.status, run.iterations, run.tool_calls, run.input_tokens + run.output_tokens,
                       seconds, run.result or run.error)
                if keep:
                    self.stdout.write(f"  kept as run {run.pk}")
                    return row
                raise Rollback
        except Rollback:
            return row
