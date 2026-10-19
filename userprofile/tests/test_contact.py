import smtplib
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from userprofile import turnstile
from userprofile.models import Comment


@override_settings(COMMENT_NOTIFICATION_EMAILS=["info@hiredlabs.org"])
class ContactCommentTest(TestCase):
    def setUp(self):
        patcher = mock.patch.object(turnstile, "verify", return_value=True)
        self.turnstile_verify = patcher.start()
        self.addCleanup(patcher.stop)

    def post_comment(self, **overrides):
        data = {"name": "Pat Doe", "email": "pat@example.com", "comment": "Hello there", **overrides}
        return self.client.post(reverse("contact"), data)

    def test_comment_is_saved_and_emailed(self):
        response = self.post_comment()
        self.assertRedirects(response, reverse("thanks"))

        comment = Comment.objects.get()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["info@hiredlabs.org"])
        self.assertEqual(message.reply_to, ["pat@example.com"])
        self.assertEqual(message.subject, "New comment from Pat Doe")
        self.assertIn("Hello there", message.body)
        self.assertIn(reverse("admin:userprofile_comment_change", args=[comment.pk]), message.body)

    def test_newline_in_name_does_not_break_subject(self):
        response = self.post_comment(name="Pat\nBcc: x@example.com")
        self.assertRedirects(response, reverse("thanks"))
        self.assertEqual(mail.outbox[0].subject, "New comment from Pat Bcc: x@example.com")

    def test_failed_send_still_saves_comment(self):
        with mock.patch("django.core.mail.EmailMessage.send", side_effect=smtplib.SMTPException), \
                self.assertLogs("userprofile.views", level="ERROR"):
            response = self.post_comment()
        self.assertRedirects(response, reverse("thanks"))
        self.assertEqual(Comment.objects.count(), 1)

    def test_bot_check_failure_sends_nothing(self):
        self.turnstile_verify.return_value = False
        response = self.post_comment()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Comment.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
