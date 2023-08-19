import requests_mock
from allauth.account.models import EmailAddress
from allauth.account.utils import has_verified_email
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from userprofile.models import OnboardingStep, Profile
from userprofile.va_api import VA_CONFIRM_ENDPOINT


def create_user(username: str, password: str) -> User:
    user = User.objects.create_user(
        username=username, email=username, password=password
    )
    email = EmailAddress.objects.create(
        user=user, email=user.username, primary=True, verified=True
    )
    return user


class OnBoardingHomeTestCase(TestCase):
    user: User = None

    # @classmethod
    def setUp(self) -> None:
        self.user = create_user("test@email.com", "testpass123")

    def test_profile_is_created_on_get(self):
        self.client.force_login(self.user)
        endpoint = reverse("userprofile:onboarding_home")
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 302)
        profile_step_endpoint = reverse("userprofile:onboarding_profile")

        self.assertEqual(response.url, profile_step_endpoint)
        self.assertTrue(Profile.objects.filter(user=self.user).exists())


class OnBoardingProfileStepTestCase(TestCase):
    user: User = None
    profile: Profile = None

    def setUp(self) -> None:
        self.user = create_user("testuser", "testpass123")
        self.profile = Profile.objects.create(user=self.user)

    @requests_mock.Mocker()
    def test_can_complete_step(self, mock):
        mock.post(VA_CONFIRM_ENDPOINT, json={"veteran_status": "confirmed"})
        self.client.force_login(self.user)
        endpoint = reverse("userprofile:onboarding_profile")
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "userprofile/onboarding_profile.html")

        data = {
            "first_name": "Test",
            "last_name": "User",
            "phone": "1234567890",
            "is_veteran": True,
            "city": "Houston",
            "state": "TX",
            "zip_code": "12345",
        }
        response = self.client.post(endpoint, data=data)
        # print(response.context["form"].errors)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("userprofile:onboarding_home"))
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.profile.onboarding_step, OnboardingStep.VETERAN_PROFILE)
        self.assertEqual(self.user.first_name, "Test")
        self.assertEqual(self.user.last_name, "User")
        self.assertEqual(self.profile.phone, "1234567890")
        self.assertEqual(self.profile.city, data["city"])
        self.assertEqual(self.profile.state, data["state"])
        self.assertEqual(self.profile.zip_code, data["zip_code"])

    def test_previous_step_redirect(self):
        self.client.force_login(self.user)
        endpoint = reverse("userprofile:onboarding_profile")
        response = self.client.post(endpoint, {"previous_step": True})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("userprofile:onboarding_home"))

    def test_invalid_form_submission(self):
        self.client.force_login(self.user)
        endpoint = reverse("userprofile:onboarding_profile")
        response = self.client.post(endpoint, data={})  # Invalid form data
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "userprofile/onboarding_profile.html")
        # ... Additional assertions about form errors ...

    @requests_mock.Mocker()
    def test_veteran_status_confirmation_error(self, mock):
        mock.post(
            VA_CONFIRM_ENDPOINT,
            status_code=400,
            json={"errors": [{"status": 400, "title": "Invalid veteran status"}]},
        )
        self.client.force_login(self.user)
        endpoint = reverse("userprofile:onboarding_profile")
        response = self.client.post(
            endpoint,
            data={
                "first_name": "Test",
                "last_name": "User",
                "phone": "1234567890",
                "is_veteran": True,
                "city": "Houston",
                "state": "TX",
                "zip_code": "12345",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "userprofile/onboarding_profile.html")
