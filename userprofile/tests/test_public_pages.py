from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from userprofile.context_processors import DONATE_URL
from userprofile.models import BootCampSession

PUBLIC_PAGES = [
    "home",
    "about",
    "how_it_works",
    "impact",
    "privacy_policy",
    "terms_of_service",
    "thanks",
    "contact",
    "account_login",
]


class PublicPagesRenderTest(TestCase):
    def test_public_pages_render_with_site_chrome(self):
        for name in PUBLIC_PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="hl-site')
                self.assertContains(response, "Fiscal agent: Stiles Hall.")
                self.assertContains(response, f'href="{reverse("how_it_works")}#boot-camp"')


class BootCampDatesTest(TestCase):
    def test_dates_to_be_announced_by_default(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Next boot camp: dates to be announced")
        self.assertContains(response, "Join the waitlist")
        self.assertNotContains(response, "Join the next boot camp")

        response = self.client.get(reverse("how_it_works"))
        self.assertContains(response, "Dates to be announced")

    def test_past_session_still_shows_to_be_announced(self):
        BootCampSession.objects.create(start_date=timezone.localdate() - timedelta(days=1))
        self.assertIsNone(BootCampSession.next_session())
        self.assertContains(self.client.get(reverse("home")), "dates to be announced")

    def test_upcoming_session_shows_its_date(self):
        start = timezone.localdate() + timedelta(days=30)
        BootCampSession.objects.create(start_date=start + timedelta(days=60))
        BootCampSession.objects.create(start_date=start)
        self.assertEqual(BootCampSession.next_session().start_date, start)

        response = self.client.get(reverse("home"))
        self.assertContains(response, f"Next boot camp starts {start:%B} {start.day}, {start.year}")
        self.assertContains(response, "Join the next boot camp")
        self.assertNotContains(response, "dates to be announced")

        response = self.client.get(reverse("how_it_works"))
        self.assertContains(response, f"Starts {start:%B} {start.day}, {start.year}")
        self.assertContains(response, "Save my seat")


class HomepageContentTest(TestCase):
    def test_homepage_leads_with_boot_camp_and_explains_donations(self):
        response = self.client.get(reverse("home"))
        content = response.content.decode()
        self.assertLess(content.index("Learn to code in six weeks"), content.index("One-on-one career support"))
        self.assertContains(response, "main/videos/optimized_720p")
        self.assertContains(response, 'type="video/mp4"')
        self.assertContains(response, "Why the donation form says Stiles Hall")
        self.assertContains(response, f'href="{DONATE_URL}"')
        self.assertContains(response, "Ariel Taylor")

    def test_services_page_sections(self):
        response = self.client.get(reverse("how_it_works"))
        for anchor in ("boot-camp", "career-support", "eligibility"):
            self.assertContains(response, f'id="{anchor}"')


class ImpactPageTest(TestCase):
    def test_impact_page_shows_figures_without_years(self):
        response = self.client.get(reverse("impact"))
        for figure in ("113", "1,500+", "72 hours"):
            self.assertContains(response, figure)
        for year in ("2023", "2024"):
            self.assertNotContains(response, year)
        self.assertNotContains(response, "impact-2024.jpg")
