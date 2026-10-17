from django.test import TestCase
from django.urls import reverse

from cold_apply.tests.factories import UserFactory


class ReleasesAccessTest(TestCase):
    """Releases views are staff-only; the only link to them is on the staff home page."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = UserFactory(is_staff=True)
        cls.user = UserFactory()

    def urls(self):
        return [
            reverse("releases:index", args=[1]),
            reverse("releases:release_create"),
            reverse("releases:confirm_create", args=[1]),
            reverse("releases:release_detail", args=[1]),
            reverse("releases:note_create", args=[1]),
            reverse("releases:confirm_note_create"),
            reverse("releases:app_create"),
            reverse("releases:submit_feedback"),
            reverse("releases:confirm_submit_feedback"),
            reverse("releases:feedback_dashboard", args=[1]),
            reverse("releases:feedback_list", args=[1]),
            reverse("releases:feedback_detail", args=[1]),
            reverse("releases:feedback_update", args=[1, 1]),
            reverse("releases:confirm_update_feedback"),
        ]

    def test_non_staff_is_forbidden(self):
        self.client.force_login(self.user)
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_anonymous_is_sent_to_login(self):
        for url in self.urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("account_login"), response["Location"])

    def test_staff_can_open_create_pages(self):
        self.client.force_login(self.staff)
        for name in ("releases:release_create", "releases:app_create", "releases:submit_feedback"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
