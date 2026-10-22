"""The old cold_apply pipeline tables that pipeline/0002_seed_flows reads from.
cold_apply/0004 drops them, so tests that run the seed recreate them from the
models as they were when it ran."""
import importlib
from functools import cache

from django.db import connection
from django.db.migrations.loader import MigrationLoader

seed = importlib.import_module("pipeline.migrations.0002_seed_flows")
final_steps = importlib.import_module("pipeline.migrations.0004_enrollment_endings")

OLD_MODELS = ("Phase", "Step", "Interaction")  # in dependency order


@cache
def old_apps():
    """The apps registry with the old cold_apply tables, as the seed migration
    saw them, and pipeline's models as they are now (0004 added a column the
    seed's own state doesn't know about)"""
    return MigrationLoader(None, ignore_no_migrations=True).project_state(("pipeline", "0004_enrollment_endings")).apps


def _current_step(apps):
    participant = apps.get_model("cold_apply", "Participant")
    return participant, participant._meta.get_field("current_step")


def create_old_tables():
    apps = old_apps()
    with connection.schema_editor() as editor:
        for name in OLD_MODELS:
            editor.create_model(apps.get_model("cold_apply", name))
        editor.add_field(*_current_step(apps))
    return apps


def drop_old_tables():
    apps = old_apps()
    with connection.schema_editor() as editor:
        editor.remove_field(*_current_step(apps))
        for name in reversed(OLD_MODELS):
            editor.delete_model(apps.get_model("cold_apply", name))


def seed_fresh_flows():
    """Seed the flows as a fresh database gets them, for TransactionTestCases,
    whose flush also empties the flows the migration created"""
    apps = create_old_tables()
    try:
        seed.seed_flows(apps)
        final_steps.add_final_steps(apps)
    finally:
        drop_old_tables()
