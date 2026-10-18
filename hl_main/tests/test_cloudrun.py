import os
import urllib.error
from unittest import mock

from django.test import SimpleTestCase

from hl_main import cloudrun


class DeterministicHostTest(SimpleTestCase):
    @mock.patch.dict(os.environ, {"K_SERVICE": "hl-stage-web"})
    @mock.patch.object(cloudrun, "_project_number", return_value="532697900391")
    def test_builds_host_from_service_project_and_region(self, _):
        self.assertEqual(
            cloudrun.deterministic_host("us-west1"), "hl-stage-web-532697900391.us-west1.run.app"
        )

    @mock.patch.dict(os.environ, {}, clear=True)
    @mock.patch.object(cloudrun, "_project_number")
    def test_none_outside_a_cloud_run_service(self, project_number):
        self.assertIsNone(cloudrun.deterministic_host("us-west1"))
        project_number.assert_not_called()

    @mock.patch.dict(os.environ, {"K_SERVICE": "hl-stage-web"})
    @mock.patch.object(cloudrun, "_project_number", side_effect=urllib.error.URLError("timed out"))
    def test_none_when_metadata_server_unreachable(self, _):
        with self.assertLogs("hl_main.cloudrun", "WARNING"):
            self.assertIsNone(cloudrun.deterministic_host("us-west1"))
