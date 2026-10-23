from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from cold_apply.models import Location
from cold_apply.tests.factories import (
    CountryFactory,
    ExperienceFactory,
    OrganizationFactory,
    ParticipantFactory,
    PositionFactory,
    StateFactory,
    UserFactory,
)
from resume.models import Concentration, Experience, Organization, Position

HTMX = {"HTTP_HX_REQUEST": "true"}


def make_participant():
    return ParticipantFactory(jobs=[], experiences=[])


class ReferenceDataTest(TestCase):
    """BUG-030: participants add companies, titles, concentrations and locations,
    and manage what they added; staff manage everything; nothing in use is deleted."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = UserFactory(is_staff=True)
        cls.owner = make_participant()
        cls.other = make_participant()
        cls.mine = OrganizationFactory(name="Acme", created_by=cls.owner.user)
        cls.theirs = OrganizationFactory(name="Globex", created_by=cls.other.user)
        cls.imported = OrganizationFactory(name="Initech")
        cls.us = CountryFactory(name="United States")
        cls.state = StateFactory(name="Texas", abbreviation="TX")

    def use(self, org, participant):
        return ExperienceFactory(participant=participant, org=org, bullets=[])

    def update_url(self, obj, kind="companies"):
        return reverse("cold_apply:update_reference", args=[kind, obj.pk])

    def delete_url(self, obj, kind="companies"):
        return reverse("cold_apply:delete_reference", args=[kind, obj.pk])

    # Create

    def test_signup_with_no_participant_cannot_create(self):
        self.client.force_login(UserFactory())
        response = self.client.post(reverse("cold_apply:create_company"), {"name": "New Co", "website": "x", "org_type": "Work"}, **HTMX)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Organization.objects.filter(name="New Co").exists())

    def test_participant_and_staff_create_and_own_it(self):
        for user, name in ((self.owner.user, "Owner Co"), (self.staff, "Staff Co")):
            with self.subTest(name=name):
                self.client.force_login(user)
                response = self.client.post(reverse("cold_apply:create_company"), {"name": name, "website": "x", "org_type": "Work"}, **HTMX)
                self.assertEqual(response.status_code, 204)
                self.assertEqual(Organization.objects.get(name=name).created_by, user)

    def test_same_name_in_another_case_reuses_the_row(self):
        self.client.force_login(self.owner.user)
        for name in ("globex", "Globex"):
            with self.subTest(name=name):
                response = self.client.post(reverse("cold_apply:create_company"), {"name": name, "website": "x", "org_type": "Work"}, **HTMX)
                self.assertEqual(response.status_code, 204)
                self.assertEqual(response["Hx-Refresh"], "true")
                self.assertEqual(Organization.objects.filter(name__iexact="globex").count(), 1)

    def test_title_and_concentration_are_reused(self):
        self.client.force_login(self.owner.user)
        PositionFactory(title="Data Analyst")
        self.client.post(reverse("cold_apply:create_title"), {"title": "data analyst"}, **HTMX)
        self.assertEqual(Position.objects.filter(title__iexact="data analyst").count(), 1)
        for _ in range(2):
            self.client.post(reverse("cold_apply:create_concentration"), {"name": "Data Science"}, **HTMX)
        self.assertEqual(Concentration.objects.filter(name="Data Science").count(), 1)

    def test_location_matches_city_in_any_case(self):
        Location.objects.create(city="Austin", state=self.state, country=self.us)
        self.client.force_login(self.owner.user)
        data = {"city": "AUSTIN", "state": self.state.pk, "country": self.us.pk}
        self.assertEqual(self.client.post(reverse("cold_apply:create_location"), data, **HTMX).status_code, 204)
        self.assertEqual(Location.objects.filter(city__iexact="austin").count(), 1)

    # List

    def test_participant_lists_only_what_they_added(self):
        self.client.force_login(self.owner.user)
        response = self.client.get(reverse("cold_apply:reference_list", args=["companies"]))
        self.assertContains(response, "Acme")
        self.assertNotContains(response, "Globex")
        self.assertNotContains(response, "Initech")

    def test_staff_list_everything_and_search(self):
        self.client.force_login(self.staff)
        url = reverse("cold_apply:reference_list", args=["companies"])
        response = self.client.get(url)
        for name in ("Acme", "Globex", "Initech"):
            self.assertContains(response, name)
        response = self.client.get(url, {"q": "glob"})
        self.assertContains(response, "Globex")
        self.assertNotContains(response, "Acme")

    def test_signup_with_no_participant_cannot_list(self):
        self.client.force_login(UserFactory())
        self.assertEqual(self.client.get(reverse("cold_apply:location_list")).status_code, 403)

    def test_unknown_kind_is_404(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("cold_apply:reference_list", args=["skills"])).status_code, 404)

    # Update

    def test_participant_renames_their_own_unshared_row(self):
        self.use(self.mine, self.owner)  # their own use doesn't count
        self.client.force_login(self.owner.user)
        response = self.client.post(self.update_url(self.mine), {"name": "Acme Corp", "website": "x", "org_type": "Work"})
        self.assertRedirects(response, reverse("cold_apply:reference_list", args=["companies"]))
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.name, "Acme Corp")

    def test_participant_cannot_edit_others_or_shared_rows(self):
        self.use(self.mine, self.other)
        self.client.force_login(self.owner.user)
        for org in (self.theirs, self.imported, self.mine):
            with self.subTest(org=org.name):
                self.assertEqual(self.client.get(self.update_url(org)).status_code, 403)
                response = self.client.post(self.update_url(org), {"name": "Changed", "website": "x", "org_type": "Work"})
                self.assertEqual(response.status_code, 403)
        self.assertFalse(Organization.objects.filter(name="Changed").exists())

    def test_staff_edit_any_row(self):
        self.use(self.theirs, self.other)
        self.client.force_login(self.staff)
        for url in (self.update_url(self.theirs), reverse("cold_apply:update_company", args=[self.imported.pk])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_rename_to_an_existing_name_is_refused(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.update_url(self.mine), {"name": "GLOBEX", "website": "x", "org_type": "Work"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.name, "Acme")

    # Delete

    def test_participant_deletes_their_own_unused_row(self):
        self.client.force_login(self.owner.user)
        response = self.client.post(self.delete_url(self.mine))
        self.assertRedirects(response, reverse("cold_apply:reference_list", args=["companies"]), fetch_redirect_response=False)
        self.assertFalse(Organization.objects.filter(pk=self.mine.pk).exists())

    def test_participant_cannot_delete_others_rows(self):
        self.client.force_login(self.owner.user)
        for org in (self.theirs, self.imported):
            with self.subTest(org=org.name):
                self.assertEqual(self.client.post(self.delete_url(org)).status_code, 404)
                self.assertTrue(Organization.objects.filter(pk=org.pk).exists())

    def test_row_in_use_is_not_deleted(self):
        experience = self.use(self.mine, self.owner)
        for user in (self.owner.user, self.staff):
            with self.subTest(user=user.email):
                self.client.force_login(user)
                response = self.client.post(self.delete_url(self.mine), follow=True)
                self.assertContains(response, "used by 1 record")
                self.assertTrue(Organization.objects.filter(pk=self.mine.pk).exists())
        self.assertTrue(Experience.objects.filter(pk=experience.pk).exists())

    def test_get_does_not_delete(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.delete_url(self.imported)).status_code, 405)
        self.assertTrue(Organization.objects.filter(pk=self.imported.pk).exists())

    def test_staff_delete_any_unused_row(self):
        location = Location.objects.create(city="Dallas", state=self.state, country=self.us)
        self.client.force_login(self.staff)
        self.client.post(self.delete_url(self.imported))
        self.client.post(self.delete_url(location, "locations"))
        self.assertFalse(Organization.objects.filter(pk=self.imported.pk).exists())
        self.assertFalse(Location.objects.filter(pk=location.pk).exists())

    def test_list_offers_delete_only_for_unused_rows(self):
        self.use(self.theirs, self.other)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("cold_apply:reference_list", args=["companies"]))
        self.assertContains(response, self.delete_url(self.imported))
        self.assertNotContains(response, self.delete_url(self.theirs))

    def test_deleting_a_company_in_use_is_protected(self):
        # Experience.org was CASCADE: one delete would remove every participant's experience there
        self.use(self.theirs, self.other)
        with self.assertRaises(ProtectedError):
            self.theirs.delete()
