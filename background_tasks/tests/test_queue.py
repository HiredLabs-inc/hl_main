from django.conf import settings
from django.http import Http404
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings

from background_tasks.models import Task, TaskStatusChoices
from background_tasks.queue import TASK_ID_HEADER, delete_task, work_task


class ProductionSettingTest(TestCase):
    def test_defined_outside_cloud_settings(self):
        self.assertFalse(settings.PRODUCTION)

    @override_settings(DEBUG=False)
    def test_delete_task_without_debug_skips_cloud_tasks(self):
        task = Task.objects.create(target_path="/", payload={})
        self.assertTrue(delete_task(task))


class WorkTaskTest(TransactionTestCase):
    """TransactionTestCase, so work_task runs outside a test transaction as it does
    in a real request (select_for_update needs one of its own)."""

    def request(self, task_id):
        return RequestFactory().post("/", headers={TASK_ID_HEADER: str(task_id)})

    def test_success_is_recorded(self):
        task = Task.objects.create(target_path="/", payload={"n": 2})
        result = work_task(self.request(task.id), lambda n: n * 2)
        task.refresh_from_db()
        self.assertEqual(result, task)
        self.assertEqual(task.status, TaskStatusChoices.SUCCESS)
        self.assertEqual(task.result, "4")

    def test_failure_is_recorded_and_logged(self):
        task = Task.objects.create(target_path="/", payload={})

        def boom():
            raise ValueError("scrape failed")

        with self.assertLogs("background_tasks.queue", level="ERROR"):
            work_task(self.request(task.id), boom)
        task.refresh_from_db()
        self.assertEqual(task.status, TaskStatusChoices.FAILURE)
        self.assertEqual(task.result, "scrape failed")

    def test_unknown_or_missing_task_is_404(self):
        for task_id in ("999", "abc", ""):
            with self.subTest(task_id=task_id):
                with self.assertRaises(Http404):
                    work_task(self.request(task_id), lambda: None)
