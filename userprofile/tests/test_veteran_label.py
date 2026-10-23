from importlib import import_module

from django.apps import apps
from django.test import TestCase
from django.urls import reverse

from cold_apply.tests.factories import ParticipantFactory
from userprofile.models import Profile

migration = import_module("userprofile.migrations.0025_service_branch_default_none")


class VeteranLabelTest(TestCase):
    """BUG-032: a veteran with no branch or rank read "Not a Veteran Veteran (None)" """

    def test_label_leaves_out_what_is_unset(self):
        cases = [
            ({"service_branch": "ARMY", "rank_at_separation": "Sergeant"}, "US Army Veteran (Sergeant)"),
            ({"service_branch": "NAVY", "rank_at_separation": None}, "US Navy Veteran"),
            ({"service_branch": None, "rank_at_separation": None}, "Veteran"),
        ]
        for fields, label in cases:
            with self.subTest(label=label):
                self.assertEqual(Profile(**fields).veteran_label, label)

    def test_new_profiles_have_no_branch(self):
        self.assertIsNone(Profile().service_branch)

    def test_participant_page(self):
        participant = ParticipantFactory(jobs=[], experiences=[])
        Profile.objects.filter(user=participant.user).update(is_veteran=True, service_branch=None, rank_at_separation=None)
        self.client.force_login(participant.user)
        response = self.client.get(reverse("cold_apply:participant_detail", args=[participant.pk]))
        self.assertNotContains(response, "Not a Veteran")
        self.assertNotContains(response, "(None)")
        self.assertContains(response, "Veteran")

    def test_migration_clears_the_old_default(self):
        participant = ParticipantFactory(jobs=[], experiences=[])
        Profile.objects.filter(user=participant.user).update(service_branch=migration.OLD_DEFAULT)
        migration.clear_old_default(apps, None)
        self.assertIsNone(Profile.objects.get(user=participant.user).service_branch)
