import os
from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from pipeline import services
from pipeline.models import Enrollment, Flow, Step
from userprofile.models import BootCampSession

from .old_pipeline import seed_fresh_flows
from .test_dashboard import person



class DashboardBrowserTest(StaticLiveServerTestCase):
    """Smoke test of the dashboard's htmx controls in a real browser"""

    @classmethod
    def setUpClass(cls):
        # Playwright's sync API runs an event loop; let Django's ORM run alongside it
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        # TransactionTestCases flush the database, including the flows seeded by migrations
        if not Flow.objects.exists():
            seed_fresh_flows()
        User.objects.create_user("staff@example.com", "staff@example.com", "password", is_staff=True)
        intake = Flow.objects.get(slug="intake")
        self.person = person("new@example.com", "Nia", "New")
        self.intake = services.enroll(self.person, intake, None, step=Step.objects.filter(phase__flow=intake).last())
        self.page = self.browser.new_page()
        self.page.goto(f"{self.live_server_url}{reverse('account_login')}?next={reverse('staff')}")
        self.page.locator("#id_login").fill("staff@example.com")
        self.page.locator("#id_password").fill("password")
        self.page.get_by_role("button", name="Sign In").click()
        expect(self.page.get_by_role("link", name="Nia New")).to_be_visible()

    def tearDown(self):
        self.page.close()

    def test_triage_move_step_and_assign_session(self):
        page = self.page
        page.get_by_role("button", name="More actions for Nia New").click()
        page.get_by_label("Boot Camp").check()
        page.get_by_role("button", name="Complete triage").click()
        expect(page.get_by_text("Triaged into Boot Camp.")).to_be_visible()
        # The table refreshed: the completed Intake enrollment is gone from the Intake tab
        expect(page.get_by_role("link", name="Nia New")).to_have_count(0)
        self.intake.refresh_from_db()
        self.assertEqual(self.intake.status, Enrollment.Status.COMPLETED)
        boot_camp = Enrollment.objects.get(person=self.person, flow__slug="boot-camp")

        first_step = boot_camp.current_step
        last_step = Step.objects.create(phase=first_step.phase, title="Send Calendar Invite", order=first_step.order + 1)
        page.goto(f"{self.live_server_url}{reverse('staff')}?tab=boot-camp")
        page.get_by_label("Step for Nia New").select_option(str(last_step.pk))
        expect(page.get_by_text(f"Moved to {last_step.title}.")).to_be_visible()
        boot_camp.refresh_from_db()
        self.assertEqual(boot_camp.current_step, last_step)
        # The actions row stays closed after the row is swapped
        actions = page.locator(f"#actions-{boot_camp.pk}")
        expect(actions).to_be_hidden()

        session = BootCampSession.objects.create(start_date=timezone.localdate() + timedelta(days=30))
        page.reload()
        page.get_by_label("Boot camp session for Nia New").select_option(str(session.pk))
        expect(page.get_by_text(f"Session set: {session.label}.")).to_be_visible()
        self.assertEqual(boot_camp.bootcamp_seat.session, session)
        expect(actions).to_be_hidden()
        page.get_by_role("button", name="More actions for Nia New").click()
        expect(actions).to_be_visible()

    def test_side_panel_opens_and_closes(self):
        page = self.page
        page.get_by_role("link", name="Nia New").click()
        dialog = page.get_by_role("dialog", name="Nia New")
        expect(dialog).to_be_visible()
        expect(dialog.get_by_text("Timeline")).to_be_visible()
        page.keyboard.press("Escape")
        expect(dialog).to_have_count(0)
