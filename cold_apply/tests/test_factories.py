from unittest import mock

from django.test import TestCase

from cold_apply.tests.factories import CountryFactory, OrganizationFactory
from resume.models import Organization

LONGEST_FAKER_COUNTRY = "British Indian Ocean Territory (Chagos Archipelago)"


class FactoryDataTest(TestCase):
    """Factory values always fit the schema, so tests and load_dev_data don't fail at random."""

    def test_country_name_fits_its_column(self):
        # BUG-020 / BUG-033: this name is 51 characters; Country.name allows 50
        with mock.patch("cold_apply.tests.factories.fake.country", return_value=LONGEST_FAKER_COUNTRY):
            country = CountryFactory()
        country.refresh_from_db()
        self.assertEqual(country.name, LONGEST_FAKER_COUNTRY[:50])

    def test_repeated_company_name_reuses_the_organization(self):
        # BUG-039: Organization.name is unique
        first = OrganizationFactory(name="Smith Inc")
        second = OrganizationFactory(name="Smith Inc")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Organization.objects.filter(name="Smith Inc").count(), 1)
