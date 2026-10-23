import json

from django.test import SimpleTestCase

from hlagents.agents import AGENT_TYPES, CORRECTABLE, ParseError, agent_type_choices, get_agent_type
from hlagents.agents.funding import FundingAgent, is_listing_or_news
from hlagents.tests.fakes import FUNDERS


class ParseTest(SimpleTestCase):
    agent = get_agent_type("funding")

    def test_plain_json(self):
        self.assertEqual(self.agent.parse(json.dumps(FUNDERS)), FUNDERS)

    def test_code_fence_and_surrounding_text(self):
        text = f"Here you go:\n```json\n{json.dumps(FUNDERS)}\n```\nGood luck!"
        self.assertEqual(self.agent.parse(text), FUNDERS)

    def test_list_wrapped_in_an_object(self):
        self.assertEqual(self.agent.parse(json.dumps({"candidates": FUNDERS})), FUNDERS)

    def test_empty_list(self):
        self.assertEqual(self.agent.parse("[]"), [])

    def test_not_json(self):
        with self.assertRaisesMessage(ParseError, "isn't valid JSON"):
            self.agent.parse("I couldn't find any.")

    def test_not_a_list_of_objects(self):
        for text in ('{"org_name": "Acme"}', '["Acme"]', "42"):
            with self.subTest(text=text), self.assertRaisesMessage(ParseError, "isn't a JSON list"):
                self.agent.parse(text)


class FundingAgentTest(SimpleTestCase):
    agent = get_agent_type("funding")

    def test_dedupe_key_is_normalized_org_name(self):
        self.assertEqual(self.agent.dedupe_key(FUNDERS[1]), "bolt giving")
        self.assertEqual(self.agent.dedupe_key({"org_name": None}), "")

    def test_to_lead(self):
        self.assertEqual(
            self.agent.to_lead(FUNDERS[0]),
            {
                "org_name": "Acme Foundation",
                "funding_amount": "50000",
                "application_deadline": "2026-12-01",
                "url": "https://acme.example.org/grants",
                "justification": "Funds workforce training for veterans.",
            },
        )


class OutreachAgentTest(SimpleTestCase):
    agent = get_agent_type("outreach")

    def test_dedupe_key_is_normalized_email(self):
        self.assertEqual(self.agent.dedupe_key({"contact_email": " Pat.Doe@VA.gov "}), "pat.doe@va.gov")

    def test_missing_or_invalid_email_has_no_key(self):
        for email in (None, "", "not an email", "pat@"):
            with self.subTest(email=email):
                self.assertEqual(self.agent.dedupe_key({"contact_email": email}), "")

    def test_to_lead_normalizes_email(self):
        lead = self.agent.to_lead(
            {"first_name": "Pat", "last_name": "Doe", "org_name": "DAV", "contact_email": "Pat@DAV.org"}
        )
        self.assertEqual(lead["contact_email"], "pat@dav.org")
        self.assertEqual(lead["justification"], "")


class RegistryTest(SimpleTestCase):
    def test_choices(self):
        self.assertEqual(
            agent_type_choices(), [("funding", "Funding opportunities"), ("outreach", "Outreach partners")]
        )

    def test_lead_kinds_are_lead_kinds(self):
        from hlagents.models import Lead

        for agent in AGENT_TYPES.values():
            self.assertIn(agent.lead_kind, Lead.Kind.values)


class ListingOrNewsTest(SimpleTestCase):
    def test_blocked(self):
        for url in [
            "https://www.instrumentl.com/browse-grants/illinois/veterans",
            "https://grantsmarts.com/top-grants-for-nonprofits-serving-veterans",
            "https://fconline.foundationcenter.org/grants/123",
            "https://www.prnewswire.com/news-releases/walmart-grants-500000.html",
            "https://newsroom.thecignagroup.com/2026-06-02-grant-program",
            "https://vystarfoundation.org/news/archive/awards-grants",
            "https://example.org/blog/our-new-grant",
        ]:
            with self.subTest(url):
                self.assertTrue(is_listing_or_news(url))

    def test_allowed(self):
        for url in [
            "https://www.woundedwarriorproject.org/programs/community-partners",
            "https://bobwoodrufffoundation.org/grants/",
            "https://www.grants.gov/search-results-detail/123456",
            "https://newsomefoundation.org/grants",
            "https://example.org/programs/newsletter-grants",
        ]:
            with self.subTest(url):
                self.assertFalse(is_listing_or_news(url))

    def test_funding_candidates_on_listings_are_rejected_for_correction(self):
        url = "https://www.instrumentl.com/grants/acme"
        candidate = {"org_name": "Acme", "application_url": url}
        self.assertEqual(FundingAgent().validate(candidate, url), "listing or news site")
        self.assertIn("listing or news site", CORRECTABLE)
