from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pipeline import services
from pipeline.models import Activity, Enrollment, Flow, Phase, Step
from pipeline.tests.test_actions import events
from pipeline.tests.test_dashboard import person
from userprofile import bootcamp
from userprofile.models import BootCampSeat, BootCampSession


class BootCampTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("staff@example.com", is_staff=True)
        cls.boot_camp = Flow.objects.get(slug="boot-camp")
        cls.job_search = Flow.objects.get(slug="resume-job-search")
        today = timezone.localdate()
        cls.past = BootCampSession.objects.create(start_date=today - timedelta(days=30))
        cls.march = BootCampSession.objects.create(start_date=today + timedelta(days=30))
        cls.june = BootCampSession.objects.create(start_date=today + timedelta(days=120))

    def setUp(self):
        self.client.force_login(self.staff)
        self.enrollment = services.enroll(person("vet@example.com", "Pat", "Vet"), self.boot_camp, None)

    def seat(self):
        return BootCampSeat.objects.filter(enrollment=self.enrollment).first()


class AssignSessionTest(BootCampTestCase):
    def test_assign_change_and_waitlist_are_on_the_timeline(self):
        bootcamp.assign_session(self.enrollment, self.march, self.staff)
        bootcamp.assign_session(self.enrollment, self.june, self.staff)
        self.assertEqual(self.seat().session, self.june)
        self.assertEqual(list(self.june.enrollments.all()), [self.enrollment])
        bootcamp.assign_session(self.enrollment, None, self.staff)
        self.assertIsNone(self.seat())
        entries = Activity.objects.filter(kind="session_change").order_by("pk")
        self.assertEqual(
            [(e.from_value, e.to_value) for e in entries],
            [("Waitlist", self.march.label), (self.march.label, self.june.label), (self.june.label, "Waitlist")],
        )
        self.assertTrue(all(e.actor == self.staff and e.enrollment == self.enrollment for e in entries))

    def test_same_session_records_nothing(self):
        bootcamp.assign_session(self.enrollment, None, self.staff)
        bootcamp.assign_session(self.enrollment, self.march, self.staff)
        bootcamp.assign_session(self.enrollment, self.march, self.staff)
        self.assertEqual(Activity.objects.filter(kind="session_change").count(), 1)

    def test_one_session_per_enrollment(self):
        BootCampSeat.objects.create(enrollment=self.enrollment, session=self.march)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BootCampSeat.objects.create(enrollment=self.enrollment, session=self.june)

    def test_only_boot_camp_enrollments(self):
        other = services.enroll(self.enrollment.person, self.job_search, None)
        with self.assertRaisesMessage(ValidationError, "Only Boot Camp"):
            bootcamp.assign_session(other, self.march, self.staff)
        self.assertFalse(BootCampSeat.objects.exists())

    def test_sessions_with_people_cant_be_deleted(self):
        bootcamp.assign_session(self.enrollment, self.march, self.staff)
        with self.assertRaises(Exception), transaction.atomic():
            self.march.delete()


class ConfirmationStepTest(BootCampTestCase):
    """A session moves people on to Send Enrollment Confirmation, unless they're
    already at or past it in On-boarding"""

    def setUp(self):
        super().setUp()
        onboarding = self.enrollment.current_step.phase
        self.start = self.enrollment.current_step
        self.confirm = Step.objects.create(phase=onboarding, title="Send Enrollment Confirmation", order=self.start.order + 1)
        self.active = Step.objects.create(phase=onboarding, title="Active Student", order=self.start.order + 2)
        wait_list = Phase.objects.create(flow=self.boot_camp, title="Boot Camp Wait List", order=onboarding.order + 1)
        self.priority = Step.objects.create(phase=wait_list, title="Priority Enrollment - Next Cycle", order=0)

    def on(self, step):
        services.move_to_step(self.enrollment, step, self.staff)
        Activity.objects.filter(kind="step_change").delete()

    def step_after_assigning(self, session):
        bootcamp.assign_session(self.enrollment, session, self.staff)
        self.enrollment.refresh_from_db()
        return self.enrollment.current_step

    def test_moves_from_earlier_steps_and_the_wait_list(self):
        for step in (self.start, self.priority):
            with self.subTest(step=step.title):
                self.on(step)
                bootcamp.assign_session(self.enrollment, None, self.staff)
                self.assertEqual(self.step_after_assigning(self.march), self.confirm)
                change = Activity.objects.get(kind="step_change")
                self.assertEqual((change.from_value, change.to_value, change.actor), (step.title, self.confirm.title, self.staff))
                Activity.objects.filter(kind="step_change").delete()

    def test_stays_at_or_past_confirmation(self):
        for step in (self.confirm, self.active):
            with self.subTest(step=step.title):
                self.on(step)
                bootcamp.assign_session(self.enrollment, None, self.staff)
                self.assertEqual(self.step_after_assigning(self.june), step)
                self.assertFalse(Activity.objects.filter(kind="step_change").exists())

    def test_waitlist_does_not_move(self):
        self.on(self.priority)
        bootcamp.assign_session(self.enrollment, self.march, self.staff)
        self.on(self.priority)
        self.assertEqual(self.step_after_assigning(None), self.priority)

    def test_ended_enrollment_gets_a_session_without_moving(self):
        """To record which cohort someone was in after the fact (BUG-037)"""
        services.set_status(self.enrollment, "withdrawn", self.staff)
        self.assertIsNone(bootcamp.assign_session(self.enrollment, self.past, self.staff))
        self.enrollment.refresh_from_db()
        self.assertEqual((self.seat().session, self.enrollment.current_step), (self.past, self.start))

    def test_toast_says_where_they_moved(self):
        response = self.client.post(reverse("pipeline:session", args=[self.enrollment.pk]), {"session": self.march.pk})
        self.assertEqual(
            events(response)["toast"]["text"], f"Session set: {self.march.label}. Moved to Send Enrollment Confirmation."
        )


class SessionActionTest(BootCampTestCase):
    def post(self, value):
        return self.client.post(reverse("pipeline:session", args=[self.enrollment.pk]), {"session": value})

    def test_set_and_clear(self):
        response = self.post(self.march.pk)
        self.assertEqual(events(response)["toast"]["text"], f"Session set: {self.march.label}.")
        self.assertTrue(events(response)["enrollment-changed"])
        self.assertContains(response, f'<option value="{self.march.pk}" selected>')
        self.assertEqual(events(self.post(""))["toast"]["text"], "Moved to the waitlist.")
        self.assertIsNone(self.seat())

    def test_bad_session_refused(self):
        for value in ("abc", "999999"):
            with self.subTest(session=value):
                response = self.post(value)
                self.assertEqual(response["HX-Reswap"], "none")
                self.assertEqual(events(response)["toast"]["text"], "Choose a session.")

    def test_staff_only(self):
        self.client.force_login(self.enrollment.person)
        self.assertEqual(self.post(self.march.pk).status_code, 403)
        self.assertIsNone(self.seat())


class DashboardTest(BootCampTestCase):
    def rows(self, **params):
        response = self.client.get(reverse("staff"), {"tab": "boot-camp", **params})
        return response, [row.person.email for row in response.context["rows"]]

    def test_session_filter(self):
        seated = services.enroll(person("seated@example.com"), self.boot_camp, None)
        bootcamp.assign_session(seated, self.march, self.staff)
        self.assertEqual(self.rows(session="waitlist")[1], ["vet@example.com"])
        self.assertEqual(self.rows(session=self.march.pk)[1], ["seated@example.com"])
        self.assertEqual(self.rows(session=self.june.pk)[1], [])
        self.assertEqual(sorted(self.rows()[1]), ["seated@example.com", "vet@example.com"])
        self.assertIn("session", self.rows()[0].context["filters"].fields)

    def test_filter_only_on_boot_camp_tab(self):
        response = self.client.get(reverse("staff"), {"tab": "resume-job-search"})
        self.assertNotIn("session", response.context["filters"].fields)
        self.assertNotContains(response, 'name="session"')

    def test_row_offers_upcoming_then_past_sessions(self):
        response, _ = self.rows()
        self.assertContains(response, "Waitlist (no session)")
        self.assertContains(response, self.march.label, count=2)  # filter and row
        self.assertContains(response, '<optgroup label="Past sessions">')
        row = response.context["rows"][0]
        self.assertEqual((row.session_choices, row.past_sessions), ([self.march, self.june], [self.past]))
        bootcamp.assign_session(self.enrollment, self.past, self.staff)
        row = self.rows()[0].context["rows"][0]
        self.assertEqual(row.session, self.past)

    def test_panel_and_timeline(self):
        bootcamp.assign_session(self.enrollment, self.march, self.staff)
        response = self.client.get(reverse("pipeline:panel", args=[self.enrollment.person.pk]))
        self.assertContains(response, f'<option value="{self.march.pk}" selected>')
        self.assertContains(response, f"Boot camp session</span>: Waitlist → {self.march.label}")


class EndingTest(BootCampTestCase):
    """Completed needs Graduated and a session that has started; Dropped needs
    a started session; Withdrawn is for people whose session hasn't (BUG-037)"""

    def setUp(self):
        super().setUp()
        self.graduated = Step.objects.get(phase__flow=self.boot_camp, completes_flow=True)

    def choices(self):
        self.enrollment.refresh_from_db()
        return services.ending_choices(self.enrollment)

    def refusal(self, status):
        self.enrollment.refresh_from_db()
        return services.ending_options(self.enrollment)[status]

    def test_before_their_session_only_withdraw(self):
        for session in (None, self.march):
            with self.subTest(session=session):
                bootcamp.assign_session(self.enrollment, session, self.staff)
                services.move_to_step(self.enrollment, self.graduated, self.staff)
                self.assertEqual(self.choices(), [Enrollment.Status.WITHDRAWN])
                self.assertEqual(self.refusal("completed"), "Give them a session that has started first.")
                self.assertIn("withdraw them instead", self.refusal("dropped"))

    def test_after_their_session_starts_drop_or_complete(self):
        bootcamp.assign_session(self.enrollment, self.past, self.staff)
        self.assertEqual(self.choices(), [Enrollment.Status.DROPPED])
        self.assertEqual(self.refusal("withdrawn"), "Their session has started; drop them instead.")
        self.assertEqual(self.refusal("completed"), "Move them to Graduated first.")
        services.move_to_step(self.enrollment, self.graduated, self.staff)
        self.assertEqual(self.choices(), [Enrollment.Status.COMPLETED, Enrollment.Status.DROPPED])
        with self.assertRaisesMessage(ValidationError, "drop them instead"):
            services.set_status(self.enrollment, "withdrawn", self.staff)
        services.set_status(self.enrollment, "dropped", self.staff)
        self.assertTrue(self.choices() == [Enrollment.Status.COMPLETED] and self.enrollment.is_ended)

    def test_fixing_a_graduate_completed_without_a_session(self):
        """The prod case: completed with no cohort, then fixed from the dashboard"""
        Enrollment.objects.filter(pk=self.enrollment.pk).update(status="completed", ended_at=timezone.now())
        self.enrollment.refresh_from_db()
        services.reopen(self.enrollment, self.staff)
        bootcamp.assign_session(self.enrollment, self.past, self.staff)
        services.move_to_step(self.enrollment, self.graduated, self.staff)
        services.set_status(self.enrollment, "completed", self.staff)
        self.enrollment.refresh_from_db()
        self.assertEqual((self.enrollment.status, self.seat().session), ("completed", self.past))
        self.assertTrue(self.enrollment.is_ended)

    def test_dashboard_buttons(self):
        bootcamp.assign_session(self.enrollment, self.past, self.staff)
        response = self.client.get(reverse("staff"), {"tab": "boot-camp"})
        self.assertContains(response, 'name="status" value="dropped"')
        self.assertNotContains(response, 'name="status" value="withdrawn"')
        self.assertNotContains(response, 'name="status" value="completed"')
