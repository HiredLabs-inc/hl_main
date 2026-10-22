from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from cold_apply.tests.factories import UserFactory


class ReleasesAccessTest(TestCase):
    """Releases views need a releases permission, managed in Django admin."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.staff = UserFactory(is_staff=True)
        cls.permitted = UserFactory(is_staff=True)
        cls.permitted.user_permissions.add(Permission.objects.get(codename="view_release"))

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

    def test_without_releases_permission_is_forbidden(self):
        for user in (self.user, self.staff):
            self.client.force_login(user)
            for url in self.urls():
                with self.subTest(user=user.email, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)

    def test_anonymous_is_sent_to_login(self):
        for url in self.urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("account_login"), response["Location"])

    def test_releases_permission_can_open_create_pages(self):
        self.client.force_login(self.permitted)
        for name in ("releases:release_create", "releases:app_create", "releases:submit_feedback"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
