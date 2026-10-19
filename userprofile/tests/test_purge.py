import csv
import os
import smtplib
import tempfile
from datetime import timedelta
from io import StringIO
from unittest import mock

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from cold_apply.models import Participant
from userprofile import purge, reminders
from userprofile.models import PendingSignup, Profile

BEFORE = "2026-10-01"


def make_user(email, joined="2026-01-01", password=None, **kwargs):
    user = User.objects.create_user(email, email, password, **kwargs)  # password=None -> unusable
    user.date_joined = timezone.make_aware(timezone.datetime.fromisoformat(joined))
    user.save()
    return user


def run(*args):
    out = StringIO()
    call_command("purge_legacy_unverified_users", f"--before={BEFORE}", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


@override_settings(PUBLIC_BASE_URL="https://example.test")
class PurgeTest(TestCase):
    def setUp(self):
        self.legacy = make_user("legacy@example.com")
        self.keep = [
            make_user("new@example.com", joined="2026-10-15"),
            make_user("haspassword@example.com", password="a-Long-unusual-passphrase-42"),
            make_user("staff@example.com", is_staff=True),
        ]
        verified = make_user("verified@example.com")
        EmailAddress.objects.create(user=verified, email=verified.email, verified=True, primary=True)
        onboarded = make_user("onboarded@example.com")
        Profile.objects.create(user=onboarded, is_onboarded=True)
        participant = make_user("participant@example.com")
        Participant.objects.create(user=participant)
        self.keep += [verified, onboarded, participant]

    def test_targets_only_legacy_unverified_accounts(self):
        before = timezone.make_aware(timezone.datetime(2026, 10, 1))
        self.assertEqual(list(purge.legacy_unverified_users(before)), [self.legacy])

    def test_dry_run_and_export_change_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.csv")
            out = run("--dry-run", f"--export={path}")
            rows = list(csv.DictReader(open(path)))
        self.assertIn("would delete legacy@example.com", out)
        self.assertEqual([r["email"] for r in rows], ["legacy@example.com"])
        self.assertEqual(User.objects.count(), 7)

    def test_delete(self):
        run()
        self.assertFalse(User.objects.filter(pk=self.legacy.pk).exists())
        self.assertEqual(User.objects.count(), 6)
        self.assertEqual(len(mail.outbox), 0)

    def test_invite_sends_working_link_then_deletes(self):
        run("--invite")
        self.assertFalse(User.objects.filter(pk=self.legacy.pk).exists())
        self.assertEqual(mail.outbox[0].to, ["legacy@example.com"])
        url = mail.outbox[0].body.split("https://example.test")[1].split()[0]
        response = self.client.get(url)
        self.assertContains(response, "Set Your Password")

    def test_invite_send_failure_keeps_account(self):
        with mock.patch("allauth.account.adapter.DefaultAccountAdapter.send_mail", side_effect=smtplib.SMTPException("down")):
            with self.assertRaises(CommandError):
                run("--invite")
        self.assertTrue(User.objects.filter(pk=self.legacy.pk).exists())
        self.assertFalse(PendingSignup.objects.exists())

    def test_batch_size(self):
        make_user("legacy2@example.com", joined="2026-02-01")
        out = run("--batch-size=1")
        self.assertIn("2 legacy account(s)", out)
        self.assertFalse(User.objects.filter(pk=self.legacy.pk).exists())
        self.assertTrue(User.objects.filter(email="legacy2@example.com").exists())

    def test_bad_date(self):
        with self.assertRaises(CommandError):
            call_command("purge_legacy_unverified_users", "--before=10/01/2026")


class PendingExpiryTest(TestCase):
    def test_daily_job_deletes_unfinished_signups_after_30_days(self):
        old = PendingSignup.objects.create(email="old@example.com")
        PendingSignup.objects.filter(pk=old.pk).update(created_at=timezone.now() - reminders.PENDING_EXPIRY - timedelta(days=1))
        PendingSignup.objects.create(email="recent@example.com")
        call_command("send_signup_reminders", stdout=StringIO())
        self.assertEqual([p.email for p in PendingSignup.objects.all()], ["recent@example.com"])
