import io

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from hlagents import services
from hlagents.models import Lead
from hlagents.tests.fakes import FUNDERS, make_config, make_run
from pipeline import services as pipeline
from pipeline.models import Activity, Enrollment, Flow, Step


def csv_file(text):
    return io.BytesIO(text.encode("utf-8"))


class LeadTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("sam@example.com", "sam@example.com", "pw", first_name="Sam", is_staff=True)

    def funding_lead(self, **kwargs):
        return Lead.objects.create(
            **{"kind": Lead.Kind.FUNDING, "dedupe_key": "acme foundation", "org_name": "Acme Foundation", **kwargs}
        )

    def outreach_lead(self, email="pat@dav.org", **kwargs):
        return Lead.objects.create(
            **{"kind": Lead.Kind.OUTREACH, "dedupe_key": email, "contact_email": email, "org_name": "DAV", **kwargs}
        )


class FoundLeadsTest(LeadTestCase):
    def test_each_new_lead_is_logged_as_found(self):
        run = make_run()
        services.save_leads(run, FUNDERS)
        activities = Activity.objects.filter(kind=Activity.Kind.LEAD_FOUND)
        self.assertEqual(activities.count(), 2)
        self.assertEqual({a.lead.org_name for a in activities}, {"Acme Foundation", "Bolt  Giving"})
        self.assertEqual(activities[0].text, f"{run.config.name}, run {run.pk}")
        self.assertEqual(activities[0].actor, run.started_by)


class ReviewTest(LeadTestCase):
    def test_review_is_logged(self):
        lead = self.funding_lead()
        services.review(lead, Lead.ReviewStatus.APPROVED, self.staff)

        lead.refresh_from_db()
        self.assertEqual(lead.review_status, "approved")
        entry = lead.activities.get(kind=Activity.Kind.REVIEW)
        self.assertEqual((entry.kind, entry.from_value, entry.to_value, entry.actor), ("review", "New", "Approved", self.staff))

    def test_same_status_is_not_logged(self):
        lead = self.funding_lead()
        services.review(lead, Lead.ReviewStatus.NEW, self.staff)
        self.assertFalse(lead.activities.exists())

    def test_unknown_status(self):
        with self.assertRaises(ValidationError):
            services.review(self.funding_lead(), "maybe", self.staff)


class UpdateLeadTest(LeadTestCase):
    def test_changes_are_saved_rekeyed_and_logged(self):
        lead = self.funding_lead(funding_amount="$50k")
        services.update_lead(
            lead, {"org_name": " Acme Fund ", "funding_amount": "", "url": "https://acme.example.org"}, self.staff
        )

        lead.refresh_from_db()
        self.assertEqual((lead.org_name, lead.dedupe_key, lead.funding_amount), ("Acme Fund", "acme fund", ""))
        entry = lead.activities.get()
        self.assertEqual(entry.kind, "lead_edited")
        self.assertEqual(
            entry.text,
            "Organization: Acme Foundation → Acme Fund\nAmount: $50k → (blank)\nURL: (blank) → https://acme.example.org",
        )

    def test_no_change_is_not_logged(self):
        lead = self.funding_lead()
        services.update_lead(lead, {"org_name": "Acme Foundation"}, self.staff)
        self.assertFalse(lead.activities.exists())

    def test_outreach_email_is_normalized_and_must_be_unique(self):
        lead = self.outreach_lead()
        self.outreach_lead("lee@vfw.org")
        services.update_lead(lead, {"contact_email": "Pat.Doe@DAV.org", "org_name": "DAV"}, self.staff)
        lead.refresh_from_db()
        self.assertEqual((lead.contact_email, lead.dedupe_key), ("pat.doe@dav.org", "pat.doe@dav.org"))

        with self.assertRaisesMessage(ValidationError, "Another lead already has this."):
            services.update_lead(lead, {"contact_email": "LEE@vfw.org", "org_name": "DAV"}, self.staff)

    def test_key_field_cant_be_blanked(self):
        with self.assertRaisesMessage(ValidationError, "needed to tell leads apart"):
            services.update_lead(self.funding_lead(), {"org_name": ""}, self.staff)


class OptOutTest(LeadTestCase):
    def test_mark_and_unmark(self):
        lead = self.outreach_lead()
        services.set_opted_out(lead, True, self.staff)
        self.assertIsNotNone(lead.opted_out_at)
        services.set_opted_out(lead, True, self.staff)
        services.set_opted_out(lead, False, self.staff)
        self.assertIsNone(lead.opted_out_at)
        self.assertEqual(
            list(lead.activities.order_by("id").values_list("kind", "to_value")),
            [("opt_out", "Opted out"), ("opt_out", "Opt-out removed")],
        )


class ReadPartnersCsvTest(TestCase):
    def test_emails_and_bounces(self):
        partners = services.read_partners_csv(
            csv_file(
                "﻿EMAIL,Status\n"
                "Pat@DAV.org,\n"
                "lee@vfw.org,Bounced\n"
                "kim@vva.org,Bounced #3\n"
                "jo@amvets.org,bounced#2\n"
                ",\n"
                "lee@vfw.org,Bounced # 4\n"
            )
        )
        self.assertEqual(partners, {"pat@dav.org": 0, "lee@vfw.org": 4, "kim@vva.org": 3, "jo@amvets.org": 2})

    def test_status_column_is_optional(self):
        self.assertEqual(services.read_partners_csv(csv_file("email\npat@dav.org\n")), {"pat@dav.org": 0})

    def test_bad_rows_are_all_reported(self):
        with self.assertRaises(ValidationError) as caught:
            services.read_partners_csv(csv_file("EMAIL,Status\npat@dav.org,Unsubscribed\nnot-an-email,\n,Bounced\n"))
        self.assertEqual(
            caught.exception.messages,
            [
                "Row 2: unknown Status 'Unsubscribed'.",
                "Row 3: not-an-email isn't an email address.",
                "Row 4: (blank) isn't an email address.",
            ],
        )

    def test_missing_email_column(self):
        with self.assertRaisesMessage(ValidationError, "needs an EMAIL column"):
            services.read_partners_csv(csv_file("Name,Status\nPat,\n"))

    def test_not_utf8(self):
        with self.assertRaisesMessage(ValidationError, "isn't a UTF-8 CSV"):
            services.read_partners_csv(io.BytesIO(b"EMAIL\n\xff\xfe\n"))


class ImportPartnersTest(LeadTestCase):
    def test_creates_approved_import_leads(self):
        counts = services.import_partners({"pat@dav.org": 0, "lee@vfw.org": 2}, self.staff)

        self.assertEqual(counts, {"created": 2, "updated": 0, "unchanged": 0})
        lee = Lead.objects.get(dedupe_key="lee@vfw.org")
        self.assertEqual(
            (lee.kind, lee.source, lee.review_status, lee.bounces, lee.contact_email),
            ("outreach", "import", "approved", 2, "lee@vfw.org"),
        )
        self.assertEqual(
            list(lee.activities.order_by("id").values_list("kind", "to_value")),
            [("lead_imported", ""), ("enrolled", "Partner")],
        )

    def test_reimport_updates_bounces_and_approves_agent_leads(self):
        found = self.outreach_lead(review_status=Lead.ReviewStatus.REJECTED)
        services.import_partners({"lee@vfw.org": 0}, self.staff)

        counts = services.import_partners({"pat@dav.org": 0, "lee@vfw.org": 1}, self.staff)

        self.assertEqual(counts, {"created": 0, "updated": 2, "unchanged": 0})
        found.refresh_from_db()
        self.assertEqual((found.review_status, found.source), ("approved", "agent"))
        self.assertEqual(Lead.objects.get(dedupe_key="lee@vfw.org").bounces, 1)
        self.assertEqual(
            services.import_partners({"pat@dav.org": 0, "lee@vfw.org": 1}, self.staff),
            {"created": 0, "updated": 0, "unchanged": 2},
        )

    def test_agents_skip_imported_partners(self):
        services.import_partners({"pat@dav.org": 0}, self.staff)
        run = make_run(make_config("outreach"))
        self.assertEqual(services.save_leads(run, [{"contact_email": "PAT@dav.org"}]), (0, 1))


class ActivityConstraintTest(LeadTestCase):
    def test_activity_needs_exactly_one_of_person_and_lead(self):
        lead = self.funding_lead()
        for kwargs in ({}, {"person": self.staff, "lead": lead}):
            with self.subTest(kwargs=list(kwargs)), self.assertRaises(IntegrityError), transaction.atomic():
                Activity.objects.create(kind=Activity.Kind.NOTE, **kwargs)


class LeadFlowTest(LeadTestCase):
    """Approved leads join the flow for their kind (docs/hlagents.md §3.6)"""

    def test_approving_enrolls_at_the_first_step(self):
        lead = self.funding_lead()
        services.review(lead, Lead.ReviewStatus.APPROVED, self.staff)

        enrollment = services.open_enrollment(lead)
        self.assertEqual((enrollment.flow.slug, enrollment.current_step.title), ("funding", "Found"))
        self.assertEqual((enrollment.person, enrollment.lead, enrollment.label), (None, lead, "Acme Foundation"))
        self.assertEqual(lead.activities.get(kind=Activity.Kind.ENROLLED).enrollment, enrollment)

    def test_rejecting_withdraws_and_approving_again_starts_over(self):
        lead = self.outreach_lead()
        services.review(lead, Lead.ReviewStatus.APPROVED, self.staff)
        first = services.open_enrollment(lead)

        services.review(lead, Lead.ReviewStatus.REJECTED, self.staff)
        first.refresh_from_db()
        self.assertEqual(first.status, Enrollment.Status.WITHDRAWN)
        self.assertIsNone(services.open_enrollment(lead))

        services.review(lead, Lead.ReviewStatus.APPROVED, self.staff)
        self.assertNotEqual(services.open_enrollment(lead), first)

    def test_back_to_new_leaves_the_enrollment(self):
        lead = self.funding_lead()
        services.review(lead, Lead.ReviewStatus.APPROVED, self.staff)
        services.review(lead, Lead.ReviewStatus.NEW, self.staff)
        self.assertIsNotNone(services.open_enrollment(lead))

    def test_inactive_flow_skips_enrollment(self):
        Flow.objects.filter(slug="funding").update(active=False)
        lead = self.funding_lead()
        services.review(lead, Lead.ReviewStatus.APPROVED, self.staff)
        self.assertIsNone(services.open_enrollment(lead))

    def test_partner_import_moves_an_enrolled_agent_lead_to_partner(self):
        lead = self.outreach_lead()
        services.review(lead, Lead.ReviewStatus.APPROVED, self.staff)
        self.assertEqual(services.open_enrollment(lead).current_step.title, "Found")

        counts = services.import_partners({"pat@dav.org": 0}, self.staff)

        self.assertEqual(counts, {"created": 0, "updated": 1, "unchanged": 0})
        self.assertEqual(services.open_enrollment(lead).current_step.title, "Partner")
        self.assertEqual(Enrollment.objects.filter(lead=lead).count(), 1)

    def test_lead_flows_are_seeded(self):
        steps = Step.objects.filter(phase__flow__slug="funding").values_list("title", flat=True)
        self.assertEqual(list(steps), ["Found", "Researching", "Applying", "Submitted", "Awarded", "Declined"])
        steps = Step.objects.filter(phase__flow__slug="outreach").values_list("title", flat=True)
        self.assertEqual(list(steps), ["Found", "Contacted", "Replied", "Partner"])
        self.assertEqual(set(Flow.objects.filter(subject="lead").values_list("slug", flat=True)), {"funding", "outreach"})
        final = Step.objects.filter(phase__flow__subject="lead", completes_flow=True).values_list("title", flat=True)
        self.assertEqual(sorted(final), ["Awarded", "Declined", "Partner"])


class StageTest(LeadTestCase):
    """Leads move through their flow from /agents/ (docs/hlagents.md §8 H6)"""

    def setUp(self):
        self.lead = self.funding_lead()
        services.review(self.lead, Lead.ReviewStatus.APPROVED, self.staff)
        self.found = Step.objects.get(phase__flow__slug="funding", title="Found")
        self.applying = Step.objects.get(phase__flow__slug="funding", title="Applying")

    def test_moves_and_logs(self):
        services.set_stage(self.lead, self.applying, self.staff, from_step=self.found)

        self.assertEqual(services.open_enrollment(self.lead).current_step, self.applying)
        change = self.lead.activities.get(kind=Activity.Kind.STEP_CHANGE)
        self.assertEqual((change.from_value, change.to_value), ("Found", "Applying"))

    def test_refuses_a_lead_that_isnt_tracked(self):
        services.review(self.lead, Lead.ReviewStatus.REJECTED, self.staff)
        with self.assertRaisesMessage(ValidationError, "Approve this lead"):
            services.set_stage(self.lead, self.applying, self.staff)

    def test_refuses_a_step_from_the_other_flow(self):
        contacted = Step.objects.get(phase__flow__slug="outreach", title="Contacted")
        with self.assertRaises(ValidationError):
            services.set_stage(self.lead, contacted, self.staff)

    def test_refuses_a_stale_move(self):
        services.set_stage(self.lead, self.applying, self.staff)
        submitted = Step.objects.get(phase__flow__slug="funding", title="Submitted")
        with self.assertRaises(pipeline.StaleStep):
            services.set_stage(self.lead, submitted, self.staff, from_step=self.found)

    def test_attach_stages(self):
        other = self.outreach_lead()
        leads = services.attach_stages([self.lead, other])

        self.assertEqual(leads[0].enrollment.current_step, self.found)
        self.assertEqual([s.title for s in leads[0].stage_steps][:2], ["Found", "Researching"])
        self.assertEqual((leads[1].enrollment, leads[1].stage_steps), (None, []))
