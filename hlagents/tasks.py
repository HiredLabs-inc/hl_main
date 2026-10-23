"""Work done by the worker service, queued through background_tasks."""
from django.db import transaction

from hlagents.loop import run_agent
from hlagents.models import AgentRun


def run_agent_task(run_id):
    """Run a queued run. A run that has already started is left alone, so a
    Cloud Tasks retry of a slow run doesn't run it twice."""
    with transaction.atomic():
        run = AgentRun.objects.select_for_update().filter(pk=run_id).first()
        if run is None or run.status != AgentRun.Status.QUEUED:
            return f"skipped ({run.status if run else 'no such run'})"
        run.status = AgentRun.Status.RUNNING
        run.save(update_fields=["status", "updated_at"])
    return run_agent(run).status
