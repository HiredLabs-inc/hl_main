import base64
import json

import requests_mock
from django.core import mail
from django.test import TestCase, override_settings

from userprofile.models import EmailSuppression

TRACKING_URL = "/anymail/postmark/tracking/"


def basic_auth(credentials="dev:dev"):
    return "Basic " + base64.b64encode(credentials.encode()).decode()


def bounce(email, bounce_type="HardBounce", inactive=True):
    return {
        "RecordType": "Bounce",
        "ID": 42,
        "Type": bounce_type,
        "TypeCode": 1,
        "MessageID": "883953f4-6105-42a2-a16a-77a8eac79483",
        "Email": email,
        "Inactive": inactive,
        "Description": "The server was unable to deliver your message",
        "Details": "smtp;550 5.1.1 user unknown",
        "BouncedAt": "2026-10-16T10:00:00Z",
        "MessageStream": "outbound",
    }


@override_settings(ANYMAIL={"WEBHOOK_SECRET": "dev:dev"})
class PostmarkTrackingWebhookTest(TestCase):
    def post_event(self, payload, auth=basic_auth()):
        headers = {"HTTP_AUTHORIZATION": auth} if auth else {}
        return self.client.post(
            TRACKING_URL, json.dumps(payload), content_type="application/json", **headers
        )

    def test_hard_bounce_suppresses_address(self):
        response = self.post_event(bounce("Gone@Example.com"))
        self.assertEqual(response.status_code, 200)
        suppression = EmailSuppression.objects.get()
        self.assertEqual(suppression.email, "gone@example.com")
        self.assertEqual(suppression.reason, "bounced")

    def test_soft_bounce_does_not_suppress(self):
        self.post_event(bounce("full@example.com", bounce_type="SoftBounce", inactive=False))
        self.assertFalse(EmailSuppression.objects.exists())

    def test_spam_complaint_suppresses_address(self):
        payload = bounce("angry@example.com", bounce_type="SpamComplaint")
        payload.update(RecordType="SpamComplaint", TypeCode=512)
        self.post_event(payload)
        self.assertEqual(EmailSuppression.objects.get().reason, "complained")

    def test_repeat_event_updates_existing_row(self):
        self.post_event(bounce("gone@example.com"))
        self.post_event(bounce("gone@example.com"))
        self.assertEqual(EmailSuppression.objects.count(), 1)

    def test_delivery_is_ignored(self):
        self.post_event(
            {
                "RecordType": "Delivery",
                "MessageID": "883953f4-6105-42a2-a16a-77a8eac79483",
                "Recipient": "ok@example.com",
                "DeliveredAt": "2026-10-16T10:00:00Z",
                "Details": "Test delivery webhook details",
                "MessageStream": "outbound",
            }
        )
        self.assertFalse(EmailSuppression.objects.exists())

    def test_rejects_missing_or_wrong_credentials(self):
        for auth in (None, basic_auth("dev:wrong")):
            response = self.post_event(bounce("gone@example.com"), auth=auth)
            self.assertNotEqual(response.status_code, 200)
        self.assertFalse(EmailSuppression.objects.exists())


@override_settings(
    EMAIL_BACKEND="anymail.backends.postmark.EmailBackend",
    ANYMAIL={"POSTMARK_SERVER_TOKEN": "test-token"},
)
class PostmarkBackendTest(TestCase):
    def test_sends_through_postmark_api(self):
        with requests_mock.Mocker() as m:
            m.post(
                "https://api.postmarkapp.com/email",
                json={
                    "To": "vet@example.com",
                    "SubmittedAt": "2026-10-16T10:00:00Z",
                    "MessageID": "0a129aee-e1cd-480d-b08d-4f48548ff48d",
                    "ErrorCode": 0,
                    "Message": "OK",
                },
            )
            sent = mail.send_mail("Hi", "Body", "info@hiredlabs.org", ["vet@example.com"])

        self.assertEqual(sent, 1)
        request = m.request_history[0]
        self.assertEqual(request.headers["X-Postmark-Server-Token"], "test-token")
        self.assertEqual(request.json()["To"], "vet@example.com")
