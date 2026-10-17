from django.conf import settings
from django.test import TestCase, override_settings

from background_tasks.models import Task
from background_tasks.queue import delete_task


class ProductionSettingTest(TestCase):
    def test_defined_outside_cloud_settings(self):
        self.assertFalse(settings.PRODUCTION)

    @override_settings(DEBUG=False)
    def test_delete_task_without_debug_skips_cloud_tasks(self):
        task = Task.objects.create(target_path="/", payload={})
        self.assertTrue(delete_task(task))
