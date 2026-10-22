import smtplib
import time
from unittest import mock

import requests_mock
from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from hl_main.adapter import CustomAccountAdapter
from userprofile import signup, turnstile
from userprofile.models import Comment, PendingSignup

PASSWORD = "a-Long-unusual-passphrase-42"


class BotCheckPassesMixin:
    """Turnstile passes unless a test patches it; rate limits start empty."""

    def setUp(self):
        super().setUp()
        cache.clear()
        patcher = mock.patch.object(turnstile, "verify", return_value=True)
        self.turnstile_verify = patcher.start()
        self.addCleanup(patcher.stop)


class SignupTest(BotCheckPassesMixin, TestCase):
    def post_email(self, email="new@example.com", **extra):
        return self.client.post(reverse("custom_account_signup"), {"email": email, **extra})

    def test_new_email_creates_no_user_and_sends_link(self):
        response = self.post_email("New@Example.com")
        self.assertRedirects(response, reverse("signup_sent"))
        self.assertFalse(User.objects.exists())
        pending = PendingSignup.objects.get()
        self.assertEqual(pending.email, "new@example.com")
        self.assertEqual(pending.send_count, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/sign-up/complete/", mail.outbox[0].body)

    def test_existing_email_gets_same_response_and_a_login_email(self):
        User.objects.create_user("old@example.com", "old@example.com", PASSWORD)
        new = self.post_email("new@example.com")
        existing = self.post_email("old@example.com")
        self.assertEqual((new.status_code, new.url), (existing.status_code, existing.url))
        self.assertFalse(PendingSignup.objects.filter(email="old@example.com").exists())
        self.assertIn("/accounts/login/", mail.outbox[1].body)
        self.assertNotIn("/accounts/sign-up/complete/", mail.outbox[1].body)

    def test_honeypot_rejects(self):
        response = self.post_email(website="http://spam.example")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "couldn&#x27;t confirm you&#x27;re a person")
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(PendingSignup.objects.exists())

    def test_failed_turnstile_rejects(self):
        self.turnstile_verify.return_value = False
        response = self.post_email()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_send_failure_is_shown_and_recorded_then_retry_works(self):
        with mock.patch("allauth.account.adapter.DefaultAccountAdapter.send_mail", side_effect=smtplib.SMTPServerDisconnected("gone")), self.assertLogs("userprofile.signup", "ERROR"):
            response = self.post_email()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Try again")
        pending = PendingSignup.objects.get()
        self.assertIn("SMTPServerDisconnected", pending.last_error)
        self.assertEqual(pending.send_count, 0)

        response = self.client.post(reverse("signup_sent"))
        self.assertContains(response, "We sent the email again")
        pending.refresh_from_db()
        self.assertEqual((pending.send_count, pending.last_error), (1, ""))

    def test_resend_and_change_email(self):
        self.post_email()
        self.client.post(reverse("signup_sent"))
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(PendingSignup.objects.get().send_count, 2)

        response = self.client.post(reverse("signup_change_email"))
        self.assertRedirects(response, reverse("custom_account_signup"))
        self.assertRedirects(self.client.get(reverse("signup_sent")), reverse("custom_account_signup"))

    def test_emails_per_address_are_limited(self):
        self.post_email()
        for _ in range(signup.EMAILS_PER_HOUR - 1):
            self.client.post(reverse("signup_sent"))
        response = self.client.post(reverse("signup_sent"))
        self.assertContains(response, "Too many emails")
        self.assertEqual(len(mail.outbox), signup.EMAILS_PER_HOUR)

    def test_allauth_signup_url_redirects(self):
        response = self.client.get("/accounts/signup/")
        self.assertRedirects(response, reverse("custom_account_signup"), fetch_redirect_response=False)


class SignupCompleteTest(BotCheckPassesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pending = PendingSignup.objects.create(email="new@example.com")
        self.url = reverse("signup_complete", args=[signup.make_token(self.pending)])

    def complete(self):
        return self.client.post(self.url, {"new_password1": PASSWORD, "new_password2": PASSWORD})

    def test_sets_password_creates_verified_user_and_logs_in(self):
        self.assertContains(self.client.get(self.url), "Set Your Password")
        response = self.complete()
        self.assertRedirects(response, reverse("userprofile:user_home"), fetch_redirect_response=False)
        user = User.objects.get(email="new@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertTrue(EmailAddress.objects.get(user=user).verified)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertIsNotNone(PendingSignup.objects.get().completed_at)

    def test_weak_password_is_rejected(self):
        response = self.client.post(self.url, {"new_password1": "password", "new_password2": "password"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_link_cannot_be_reused(self):
        self.complete()
        self.client.logout()
        self.assertContains(self.client.get(self.url), "Already Used")
        self.complete()
        self.assertEqual(User.objects.count(), 1)

    def test_signup_again_after_account_deleted(self):
        # Regression: a completed PendingSignup made every new link show "Already Used".
        self.complete()
        self.client.logout()
        User.objects.get(email="new@example.com").delete()
        self.client.post(reverse("custom_account_signup"), {"email": "new@example.com"})
        new_url = mail.outbox[-1].body.split("testserver")[1].split()[0]

        self.assertContains(self.client.get(self.url), "Doesn't Work")  # the old link stays dead
        self.client.post(new_url, {"new_password1": PASSWORD, "new_password2": PASSWORD})
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    def test_link_for_deleted_pending_signup(self):
        self.pending.delete()
        self.assertContains(self.client.get(self.url), "Doesn't Work")

    def test_expired_link_offers_a_new_one(self):
        with mock.patch("django.core.signing.time.time", return_value=time.time() - signup.LINK_MAX_AGE - 60):
            url = reverse("signup_complete", args=[signup.make_token(self.pending)])
        response = self.client.get(url)
        self.assertContains(response, "Expired")
        self.assertContains(response, "?email=new%40example.com")

    def test_tampered_link(self):
        response = self.client.get(reverse("signup_complete", args=["not-a-signed-token"]))
        self.assertContains(response, "Doesn't Work")


class OtherBotCheckedFormsTest(BotCheckPassesMixin, TestCase):
    def test_password_reset_requires_bot_check(self):
        self.turnstile_verify.return_value = False
        response = self.client.post(reverse("account_reset_password"), {"email": "a@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

        self.turnstile_verify.return_value = True
        self.client.post(reverse("account_reset_password"), {"email": "a@example.com"})
        self.assertEqual(len(mail.outbox), 1)

    def test_contact_form_requires_bot_check(self):
        data = {"name": "A", "email": "a@example.com", "comment": "hi"}
        self.client.post(reverse("contact"), {**data, "website": "x"})
        self.assertFalse(Comment.objects.exists())
        self.assertRedirects(self.client.post(reverse("contact"), data), reverse("thanks"))


class TurnstileTest(SimpleTestCase):
    @override_settings(TURNSTILE_SECRET_KEY="secret")
    def test_verify_posts_token_and_reads_success(self):
        with requests_mock.Mocker() as m:
            m.post(turnstile.VERIFY_URL, json={"success": True})
            self.assertTrue(turnstile.verify("token", "1.2.3.4"))
            self.assertIn("remoteip=1.2.3.4", m.last_request.text)
            m.post(turnstile.VERIFY_URL, json={"success": False})
            self.assertFalse(turnstile.verify("token"))

    def test_missing_token_and_network_errors_fail_closed(self):
        self.assertFalse(turnstile.verify(""))
        with requests_mock.Mocker() as m, self.assertLogs("userprofile.turnstile", "WARNING"):
            m.post(turnstile.VERIFY_URL, exc=turnstile.requests.ConnectionError)
            self.assertFalse(turnstile.verify("token"))


class ClientIpTest(SimpleTestCase):
    def test_uses_last_forwarded_for_entry(self):
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="6.6.6.6, 1.2.3.4")
        self.assertEqual(CustomAccountAdapter().get_client_ip(request), "1.2.3.4")

    def test_falls_back_to_remote_addr(self):
        request = RequestFactory().get("/", REMOTE_ADDR="1.2.3.4")
        self.assertEqual(CustomAccountAdapter().get_client_ip(request), "1.2.3.4")
