import smtplib
from datetime import timedelta
from io import StringIO
from unittest import mock

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from userprofile import reminders
from userprofile.models import OnboardingReminder, PendingSignup, Profile

PASSWORD = "a-Long-unusual-passphrase-42"


def make_user(email, days_ago, verified=True, onboarded=False, **kwargs):
    user = User.objects.create_user(email, email, PASSWORD, **kwargs)
    user.date_joined = timezone.now() - timedelta(days=days_ago)
    user.save()
    EmailAddress.objects.create(user=user, email=email, verified=verified, primary=True)
    if onboarded:
        Profile.objects.create(user=user, is_onboarded=True)
    return user


def make_pending(email, sent_hours_ago, **kwargs):
    pending = PendingSignup.objects.create(email=email, send_count=1, **kwargs)
    pending.last_sent_at = timezone.now() - timedelta(hours=sent_hours_ago)
    pending.save()
    return pending


@override_settings(PUBLIC_BASE_URL="https://example.test")
class ReminderSelectionTest(TestCase):
    def test_pending_reminded_once_after_a_day(self):
        due = make_pending("due@example.com", 25)
        make_pending("recent@example.com", 2)
        make_pending("done@example.com", 48, completed_at=timezone.now())
        make_pending("reminded@example.com", 48, reminder_sent_at=timezone.now())
        self.assertEqual(list(reminders.pending_due()), [due])

        call_command("send_signup_reminders", stdout=StringIO())
        self.assertEqual([m.to for m in mail.outbox], [["due@example.com"]])
        self.assertIn("https://example.test/accounts/sign-up/complete/", mail.outbox[0].body)
        self.assertEqual(list(reminders.pending_due()), [])

    def test_unfinished_users_reminded_at_3_and_14_days(self):
        day4 = make_user("day4@example.com", 4)
        make_user("day1@example.com", 1)
        make_user("onboarded@example.com", 10, onboarded=True)
        make_user("unverified@example.com", 10, verified=False)
        make_user("staff@example.com", 10, is_staff=True)
        make_user("legacy@example.com", 400)
        self.assertEqual(reminders.users_due(), [day4])

        call_command("send_signup_reminders", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://example.test/accounts/login/", mail.outbox[0].body)
        self.assertEqual(reminders.users_due(), [])

        # 11 days later: day4's second reminder is due (and day1's first).
        later = timezone.now() + timedelta(days=11)
        self.assertIn(day4, reminders.users_due(later))
        OnboardingReminder.objects.filter(user=day4).update(sent_count=2)
        self.assertNotIn(day4, reminders.users_due(later))

    def test_dry_run_sends_nothing(self):
        make_pending("due@example.com", 25)
        out = StringIO()
        call_command("send_signup_reminders", "--dry-run", stdout=out)
        self.assertIn("would remind due@example.com", out.getvalue())
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(PendingSignup.objects.get().reminder_sent_at)

    def test_failures_are_reported_and_others_still_sent(self):
        make_pending("a@example.com", 25)
        make_user("b@example.com", 4)
        with mock.patch.object(reminders, "send_pending_reminder", side_effect=smtplib.SMTPException("down")), \
                self.assertLogs("userprofile.reminders", "ERROR"), self.assertRaises(CommandError):
            call_command("send_signup_reminders", stdout=StringIO())
        self.assertEqual([m.to for m in mail.outbox], [["b@example.com"]])


class StuckSignupsPageTest(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff@example.com", "staff@example.com", PASSWORD, is_staff=True)
        self.pending = make_pending("pending@example.com", 30, last_error="SMTP down")
        self.stuck = make_user("stuck@example.com", 5)

    def action(self, kind, pk, action):
        return self.client.post(reverse("stuck_signup_action", args=[kind, pk, action]), follow=True)

    def test_staff_only(self):
        self.assertEqual(self.client.get(reverse("stuck_signups")).status_code, 302)
        self.client.force_login(self.stuck)
        self.assertEqual(self.client.get(reverse("stuck_signups")).status_code, 403)
        self.assertEqual(self.client.post(reverse("stuck_signup_action", args=["user", self.stuck.pk, "delete"])).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.stuck.pk).exists())

    def test_lists_pending_and_unfinished(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("stuck_signups"))
        self.assertContains(response, "pending@example.com")
        self.assertContains(response, "SMTP down")
        self.assertContains(response, "stuck@example.com")
        self.assertNotContains(response, "<td class=\"td\">staff@example.com")

    def test_actions(self):
        self.client.force_login(self.staff)
        self.assertContains(self.action("pending", self.pending.pk, "resend"), "Sent a new signup link")
        self.assertContains(self.action("user", self.stuck.pk, "remind"), "Sent an onboarding reminder")
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(OnboardingReminder.objects.get(user=self.stuck).sent_count, 1)

        self.action("pending", self.pending.pk, "delete")
        self.action("user", self.stuck.pk, "delete")
        self.assertFalse(PendingSignup.objects.exists())
        self.assertFalse(User.objects.filter(pk=self.stuck.pk).exists())

    def test_cannot_delete_staff_or_onboarded_users(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse("stuck_signup_action", args=["user", self.staff.pk, "delete"])).status_code, 404)
