import shutil
import tempfile
from unittest import mock

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from cold_apply.models import Participant
from userprofile import turnstile
from userprofile.models import Profile

PASSWORD = "a-Long-unusual-passphrase-42"
MEDIA_ROOT = tempfile.mkdtemp()


def profile_data():
    return {
        "first_name": "Pat",
        "last_name": "Lee",
        "city": "Portland",
        "state": "OR",
        "phone": "555-0100",
        "linkedin": "https://www.linkedin.com/in/pat",
        "service_branch": "ARMY",
        "military_specialiaty": "11B",
        "years_of_service": 4,
        "rank_at_separation": "E-4",
        "resume": SimpleUploadedFile("resume.pdf", b"%PDF-1.4", content_type="application/pdf"),
        "service_doc": SimpleUploadedFile("dd214.pdf", b"%PDF-1.4", content_type="application/pdf"),
    }


def verified_user(email="vet@example.com", **kwargs):
    user = User.objects.create_user(email, email, PASSWORD, **kwargs)
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class OnboardingTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_requires_verified_email(self):
        user = User.objects.create_user("u@example.com", "u@example.com", PASSWORD)
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("userprofile:onboarding_view")), reverse("account_verified_email_required"))

    def test_completing_onboarding_creates_participant(self):
        user = verified_user()
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("userprofile:onboarding_view")).status_code, 200)
        response = self.client.post(reverse("userprofile:onboarding_view"), profile_data())
        self.assertRedirects(response, reverse("welcome"))
        self.assertTrue(Profile.objects.get(user=user).is_onboarded)
        self.assertTrue(Participant.objects.filter(user=user).exists())

    def test_user_home_routes_by_role(self):
        cases = [
            (verified_user("staff@example.com", is_staff=True), reverse("staff")),
            (verified_user("new@example.com"), reverse("userprofile:onboarding_view")),
        ]
        done = verified_user("done@example.com")
        Profile.objects.create(user=done, is_onboarded=True)
        cases.append((done, reverse("welcome")))
        for user, target in cases:
            self.client.force_login(user)
            self.assertRedirects(self.client.get(reverse("userprofile:user_home")), target, fetch_redirect_response=False)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SignupToOnboardingTest(TestCase):
    """The whole path: email -> link -> password -> onboarding -> welcome."""

    def setUp(self):
        cache.clear()
        patcher = mock.patch.object(turnstile, "verify", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_full_signup(self):
        self.client.post(reverse("custom_account_signup"), {"email": "vet@example.com"})
        link = mail.outbox[0].body.split("http://testserver")[1].split()[0]
        response = self.client.post(link, {"new_password1": PASSWORD, "new_password2": PASSWORD}, follow=True)
        self.assertEqual(response.redirect_chain[-1][0], reverse("userprofile:onboarding_view"))
        response = self.client.post(reverse("userprofile:onboarding_view"), profile_data(), follow=True)
        self.assertEqual(response.redirect_chain[-1][0], reverse("welcome"))

        self.client.post(reverse("account_logout"))
        response = self.client.post(reverse("account_login"), {"login": "vet@example.com", "password": PASSWORD}, follow=True)
        self.assertEqual(response.redirect_chain[-1][0], reverse("welcome"))

    def test_logged_in_user_is_sent_away_from_signup(self):
        self.client.force_login(verified_user())
        self.assertRedirects(self.client.get(reverse("custom_account_signup")), reverse("userprofile:user_home"), fetch_redirect_response=False)


class StaffOnlyUserprofilePagesTest(TestCase):
    def setUp(self):
        self.vet = verified_user()
        Profile.objects.create(user=self.vet)
        self.other = verified_user("other@example.com")
        self.pages = [reverse("staff"), reverse("userprofile:veteran_status_update_view", args=[self.vet.pk])]

    def test_anonymous_sent_to_login(self):
        for url in self.pages:
            self.assertTrue(self.client.get(url).url.startswith(reverse("account_login")), url)

    def test_non_staff_forbidden_including_own_veteran_status(self):
        for user in (self.other, self.vet):
            self.client.force_login(user)
            for url in self.pages:
                self.assertEqual(self.client.get(url).status_code, 403, url)
            response = self.client.post(self.pages[1], {"veteran_verified": "on"})
            self.assertEqual(response.status_code, 403)
        self.assertFalse(Profile.objects.get(user=self.vet).veteran_verified)

    def test_staff_allowed_on_staff_home_only(self):
        # Veteran status needs review_veteran_status as well (test_service_doc.py)
        self.client.force_login(verified_user("staff@example.com", is_staff=True))
        self.assertEqual(self.client.get(self.pages[0]).status_code, 200)
        self.assertEqual(self.client.get(self.pages[1]).status_code, 403)
