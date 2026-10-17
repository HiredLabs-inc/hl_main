from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from cold_apply.tests.factories import UserFactory


class RatesAccessTest(TestCase):
    """Rates views need a rates permission, matching the perms.rates nav link."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.staff = UserFactory(is_staff=True)
        cls.permitted = UserFactory(is_staff=True)
        cls.permitted.user_permissions.add(Permission.objects.get(codename="view_raterequest"))

    def urls(self):
        return [reverse("rates:nothingness"), reverse("rates:world_rates"), reverse("rates:index")]

    def test_without_rates_permission_is_forbidden(self):
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

    def test_rates_permission_can_open(self):
        self.client.force_login(self.permitted)
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
