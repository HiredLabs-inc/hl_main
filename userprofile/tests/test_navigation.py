from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

PASSWORD = "a-Long-unusual-passphrase-42"
LOGOUT_FORM = f'<form method="post" action="{reverse("account_logout")}"'


class HomeNavTest(TestCase):
    def test_logged_out_shows_login_and_signup(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, f'href="{reverse("account_login")}"')
        self.assertContains(response, f'href="{reverse("custom_account_signup")}"')
        self.assertNotContains(response, LOGOUT_FORM)

    def test_logged_in_shows_my_account_and_logout_button(self):
        self.client.force_login(User.objects.create_user("a@example.com", "a@example.com", PASSWORD))
        response = self.client.get(reverse("home"))
        self.assertContains(response, f'href="{reverse("userprofile:user_home")}"')
        self.assertContains(response, LOGOUT_FORM)
        self.assertNotContains(response, f'href="{reverse("account_logout")}"')


class LoginTest(TestCase):
    def test_login_page_links_to_signup_and_reset(self):
        response = self.client.get(reverse("account_login"))
        self.assertContains(response, f'href="{reverse("custom_account_signup")}"')
        self.assertContains(response, f'href="{reverse("account_reset_password")}"')

    def test_staff_login_lands_on_staff_page(self):
        User.objects.create_user("staff@example.com", "staff@example.com", PASSWORD, is_staff=True)
        response = self.client.post(reverse("account_login"), {"login": "staff@example.com", "password": PASSWORD}, follow=True)
        self.assertEqual(response.redirect_chain[-1][0], reverse("staff"))
        self.assertContains(response, LOGOUT_FORM)


class WelcomeTest(TestCase):
    def test_done_does_not_log_out(self):
        self.client.force_login(User.objects.create_user("a@example.com", "a@example.com", PASSWORD))
        response = self.client.get(reverse("welcome"))
        self.assertNotContains(response, 'type="submit">Done')
        self.assertContains(response, f'href="{reverse("home")}" class="auth-primary-button">Done')


class LogoutTest(TestCase):
    def test_get_does_not_log_out_and_post_does(self):
        self.client.force_login(User.objects.create_user("a@example.com", "a@example.com", PASSWORD))
        self.client.get(reverse("account_logout"))
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("account_logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
