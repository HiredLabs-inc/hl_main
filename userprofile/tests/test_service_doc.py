import shutil
import tempfile
from unittest import mock

from django.contrib import admin
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from cold_apply.models import Participant
from userprofile.models import Profile, VeteranProfile

from .test_onboarding import verified_user

MEDIA_ROOT = tempfile.mkdtemp()


def reviewer(email="reviewer@example.com"):
    user = verified_user(email, is_staff=True)
    user.groups.add(Group.objects.get(name="Veteran reviewers"))
    return user


@override_settings(MEDIA_ROOT=MEDIA_ROOT, GS_BUCKET_NAME="test-bucket")
class ServiceDocAccessTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.vet = verified_user()
        self.profile = Profile.objects.create(user=self.vet)
        self.profile.service_doc.save("dd214.pdf", ContentFile(b"%PDF-1.4"))
        self.doc_url = reverse("service_doc", args=[self.vet.pk])
        self.status_url = reverse("userprofile:veteran_status_update_view", args=[self.vet.pk])

    def test_migration_created_reviewer_group(self):
        group = Group.objects.get(name="Veteran reviewers")
        self.assertEqual(list(group.permissions.values_list("codename", flat=True)), ["review_veteran_status"])

    def test_new_uploads_go_to_service_docs(self):
        self.assertTrue(self.profile.service_doc.name.startswith("service_docs/"))

    def test_anonymous_sent_to_login(self):
        for url in (self.doc_url, self.status_url):
            self.assertTrue(self.client.get(url).url.startswith(reverse("account_login")), url)

    def test_staff_without_permission_forbidden(self):
        self.client.force_login(verified_user("staff@example.com", is_staff=True))
        for url in (self.doc_url, self.status_url):
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.client.post(self.status_url, {"veteran_verified": "on"})
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.veteran_verified)

    def test_owner_cannot_open_own_doc_here(self):
        self.client.force_login(self.vet)
        self.assertEqual(self.client.get(self.doc_url).status_code, 403)

    def test_permission_without_staff_forbidden(self):
        user = verified_user("notstaff@example.com")
        user.groups.add(Group.objects.get(name="Veteran reviewers"))
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.doc_url).status_code, 403)

    @mock.patch("userprofile.views.generate_signed_url", return_value="https://storage.example/signed")
    def test_reviewer_redirected_to_short_signed_url_and_logged(self, signed_url):
        self.client.force_login(reviewer())
        with self.assertLogs("hl_main.audit", level="INFO") as logs:
            response = self.client.get(self.doc_url)
        self.assertRedirects(response, "https://storage.example/signed", fetch_redirect_response=False)
        self.assertEqual(signed_url.call_args.kwargs["object_name"], self.profile.service_doc.name)
        self.assertEqual(signed_url.call_args.kwargs["expiration"], 600)
        self.assertIn(f"user {self.vet.pk}", logs.output[0])

    @mock.patch("userprofile.views.generate_signed_url", return_value="https://storage.example/signed")
    def test_superuser_allowed(self, signed_url):
        superuser = verified_user("super@example.com", is_staff=True, is_superuser=True)
        self.client.force_login(superuser)
        self.assertEqual(self.client.get(self.doc_url).status_code, 302)
        self.assertEqual(self.client.get(self.status_url).status_code, 200)

    # INTERNAL_IPS=[] keeps the debug toolbar (dev settings) out of the response
    @override_settings(DEBUG=True, INTERNAL_IPS=[])
    def test_debug_streams_local_file(self):
        self.client.force_login(reviewer())
        response = self.client.get(self.doc_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4")

    def test_missing_doc_404(self):
        self.profile.service_doc = None
        self.profile.save()
        self.client.force_login(reviewer())
        self.assertEqual(self.client.get(self.doc_url).status_code, 404)

    def test_reviewer_can_update_status_and_page_links_through_view(self):
        self.client.force_login(reviewer())
        response = self.client.get(self.status_url)
        self.assertContains(response, self.doc_url)
        self.assertNotContains(response, self.profile.service_doc.name)


class VeteranStatusButtonTest(TestCase):
    def setUp(self):
        self.vet = verified_user()
        Profile.objects.create(user=self.vet, is_veteran=True)
        self.participant = Participant.objects.create(user=self.vet)
        self.url = reverse("cold_apply:participant_detail", args=[self.participant.pk])
        self.status_url = reverse("userprofile:veteran_status_update_view", args=[self.vet.pk])

    def test_button_only_for_reviewers(self):
        for user, shown in (
            (verified_user("staff@example.com", is_staff=True), False),
            (reviewer(), True),
            (verified_user("super@example.com", is_staff=True, is_superuser=True), True),
        ):
            with self.subTest(user=user.email):
                self.client.force_login(user)
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 200)
                (self.assertContains if shown else self.assertNotContains)(response, self.status_url)


class ServiceDocAdminTest(TestCase):
    def setUp(self):
        self.vet = verified_user()

    def fields_for(self, user, model):
        request = RequestFactory().get("/")
        request.user = user
        return admin.site._registry[model].get_form(request).base_fields

    def test_field_hidden_without_permission(self):
        staff = verified_user("staff@example.com", is_staff=True)
        for model in (Profile, VeteranProfile):
            with self.subTest(model=model.__name__):
                self.assertNotIn("service_doc", self.fields_for(staff, model))

    def test_field_shown_to_reviewer(self):
        user = reviewer()
        for model in (Profile, VeteranProfile):
            with self.subTest(model=model.__name__):
                self.assertIn("service_doc", self.fields_for(user, model))

    def test_profile_admin_search_works(self):
        Profile.objects.create(user=self.vet, city="Tacoma", state="WA")
        superuser = verified_user("super@example.com", is_staff=True, is_superuser=True)
        self.client.force_login(superuser)
        for model in ("profile", "veteranprofile"):
            with self.subTest(model=model):
                response = self.client.get(reverse(f"admin:userprofile_{model}_changelist"), {"q": "vet"})
                self.assertEqual(response.status_code, 200)
