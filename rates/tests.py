from django.test import TestCase
from django.urls import reverse

from cold_apply.tests.factories import UserFactory


class RatesAccessTest(TestCase):
    """Rates views are staff-only, matching the perms.rates nav link."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = UserFactory(is_staff=True)
        cls.user = UserFactory()

    def urls(self):
        return [reverse("rates:nothingness"), reverse("rates:world_rates"), reverse("rates:index")]

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

    def test_staff_can_open(self):
        self.client.force_login(self.staff)
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
