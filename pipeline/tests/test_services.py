from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from pipeline import services
from pipeline.models import Activity, Enrollment, Flow, Phase, Step

VETERAN_REVIEW = "userprofile.review_veteran_status"


def make_user(email, **kwargs):
    return User.objects.create_user(email, email, "password", **kwargs)


class PipelineTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.intake = Flow.objects.create(name="Intake", slug="test-intake", order=0)
        applicants = Phase.objects.create(flow=cls.intake, title="Applicants")
        cls.verify = Step.objects.create(
            phase=applicants, title="Verify Veteran Status", order=0, required_permission=VETERAN_REVIEW
        )
        cls.triage = Step.objects.create(phase=applicants, title="Triage", order=1)

        cls.job_search = Flow.objects.create(name="Resume & Job Search", slug="test-job-search", order=1)
        phase_2 = Phase.objects.create(flow=cls.job_search, title="Phase 2", order=1)
        phase_1 = Phase.objects.create(flow=cls.job_search, title="Phase 1", order=0)
        cls.job_list = Step.objects.create(phase=phase_2, title="Create Initial Job List", order=0)
        cls.first_email = Step.objects.create(phase=phase_1, title="Send Initial Email", order=0)

        cls.boot_camp = Flow.objects.create(name="Boot Camp", slug="test-boot-camp", order=2)
        cls.waitlist = Step.objects.create(
            phase=Phase.objects.create(flow=cls.boot_camp, title="Wait List"), title="Priority Enrollment"
        )

        cls.person = make_user("vet@example.com", first_name="Pat", last_name="Vet")
        cls.staff = make_user("staff@example.com", is_staff=True, first_name="Sam", last_name="Staff")
        cls.reviewer = make_user("reviewer@example.com", is_staff=True)
        cls.reviewer.groups.add(Group.objects.get(name="Veteran reviewers"))


class EnrollTest(PipelineTestCase):
    def test_starts_on_first_step_by_phase_then_step_order(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        self.assertEqual(enrollment.current_step, self.first_email)
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)
        self.assertIsNotNone(enrollment.step_entered_at)
        activity = Activity.objects.get(enrollment=enrollment)
        self.assertEqual((activity.kind, activity.to_value, activity.actor), ("enrolled", "Send Initial Email", self.staff))

    def test_explicit_step_and_assignee(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff, step=self.job_list, assignee=self.staff)
        self.assertEqual((enrollment.current_step, enrollment.assignee), (self.job_list, self.staff))
        self.assertEqual(
            list(enrollment.activities.order_by("id").values_list("kind", flat=True)), ["enrolled", "assignee_change"]
        )

    def test_step_from_another_flow_refused(self):
        with self.assertRaises(ValidationError):
            services.enroll(self.person, self.job_search, self.staff, step=self.triage)

    def test_non_staff_assignee_refused(self):
        with self.assertRaises(ValidationError):
            services.enroll(self.person, self.job_search, self.staff, assignee=self.person)

    def test_one_open_enrollment_per_flow(self):
        services.enroll(self.person, self.job_search, self.staff)
        with self.assertRaises(services.AlreadyEnrolled):
            services.enroll(self.person, self.job_search, self.staff)
        self.assertEqual(Enrollment.objects.filter(person=self.person).count(), 1)

    def test_can_reenroll_after_enrollment_ends(self):
        first = services.enroll(self.person, self.job_search, self.staff)
        services.set_status(first, Enrollment.Status.WITHDRAWN, self.staff)
        second = services.enroll(self.person, self.job_search, self.staff)
        self.assertNotEqual(first.pk, second.pk)

    def test_concurrent_flows_allowed(self):
        services.enroll(self.person, self.job_search, self.staff)
        services.enroll(self.person, self.boot_camp, self.staff)
        self.assertEqual(Enrollment.objects.filter(person=self.person, ended_at__isnull=True).count(), 2)

    def test_flow_without_steps_refused(self):
        empty = Flow.objects.create(name="Empty", slug="empty")
        with self.assertRaises(ValidationError):
            services.enroll(self.person, empty, self.staff)


class MoveToStepTest(PipelineTestCase):
    def test_moves_and_records(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        entered = enrollment.step_entered_at
        enrollment = services.move_to_step(enrollment, self.job_list, self.staff)
        self.assertEqual(enrollment.current_step, self.job_list)
        self.assertGreater(enrollment.step_entered_at, entered)
        activity = enrollment.activities.get(kind="step_change")
        self.assertEqual((activity.from_value, activity.to_value), ("Send Initial Email", "Create Initial Job List"))

    def test_same_step_is_a_no_op(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        services.move_to_step(enrollment, self.first_email, self.staff)
        self.assertFalse(enrollment.activities.filter(kind="step_change").exists())

    def test_step_from_another_flow_refused(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        with self.assertRaises(ValidationError):
            services.move_to_step(enrollment, self.triage, self.staff)

    def test_permission_needed_to_leave_gated_step(self):
        enrollment = services.enroll(self.person, self.intake, self.staff)
        self.assertEqual(enrollment.current_step, self.verify)
        with self.assertRaises(PermissionDenied):
            services.move_to_step(enrollment, self.triage, self.staff)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.current_step, self.verify)
        services.move_to_step(enrollment, self.triage, self.reviewer)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.current_step, self.triage)

    def test_superuser_can_leave_gated_step(self):
        superuser = make_user("super@example.com", is_staff=True, is_superuser=True)
        enrollment = services.enroll(self.person, self.intake, self.staff)
        services.move_to_step(enrollment, self.triage, superuser)

    def test_ended_enrollment_cannot_move(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        services.set_status(enrollment, Enrollment.Status.WITHDRAWN, self.staff)
        with self.assertRaises(ValidationError):
            services.move_to_step(enrollment, self.job_list, self.staff)


class AssignTest(PipelineTestCase):
    def test_assign_change_and_clear(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        services.assign(enrollment, self.staff, self.staff)
        services.assign(enrollment, self.reviewer, self.staff)
        enrollment = services.assign(enrollment, None, self.staff)
        self.assertIsNone(enrollment.assignee)
        changes = list(enrollment.activities.filter(kind="assignee_change").order_by("id").values_list("from_value", "to_value"))
        self.assertEqual(
            changes,
            [("", "Sam Staff"), ("Sam Staff", "reviewer@example.com"), ("reviewer@example.com", "")],
        )

    def test_same_assignee_is_a_no_op(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff, assignee=self.staff)
        services.assign(enrollment, self.staff, self.staff)
        self.assertEqual(enrollment.activities.filter(kind="assignee_change").count(), 1)

    def test_non_staff_and_inactive_refused(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        inactive = make_user("gone@example.com", is_staff=True, is_active=False)
        for user in (self.person, inactive):
            with self.subTest(user=user.email), self.assertRaises(ValidationError):
                services.assign(enrollment, user, self.staff)


class SetStatusTest(PipelineTestCase):
    def test_soft_rejection_needs_reason_and_can_be_undone(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        with self.assertRaises(ValidationError):
            services.set_status(enrollment, Enrollment.Status.REJECTED, self.staff, reason="  ")
        services.set_status(enrollment, Enrollment.Status.REJECTED, self.staff, reason="Unclear DD214")
        enrollment = services.set_status(enrollment, Enrollment.Status.ACTIVE, self.staff)
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)
        self.assertIsNone(enrollment.ended_at)
        self.assertEqual(enrollment.current_step, self.first_email)
        rejection = enrollment.activities.filter(kind="status_change").order_by("id").first()
        self.assertEqual((rejection.text, rejection.from_value, rejection.to_value), ("Unclear DD214", "Active", "Rejected"))

    def test_paused_and_no_show_stay_open(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        for status in (Enrollment.Status.PAUSED, Enrollment.Status.NO_SHOW):
            enrollment = services.set_status(enrollment, status, self.staff)
            self.assertIsNone(enrollment.ended_at)

    def final_step(self):
        return Step.objects.create(phase=self.job_list.phase, title="Service Complete", order=1, completes_flow=True)

    def test_completed_only_from_a_final_step(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        with self.assertRaisesMessage(ValidationError, "can't be completed"):
            services.set_status(enrollment, Enrollment.Status.COMPLETED, self.staff)
        final = self.final_step()
        with self.assertRaisesMessage(ValidationError, "Move them to Service Complete first."):
            services.set_status(enrollment, Enrollment.Status.COMPLETED, self.staff)
        self.assertEqual(services.ending_choices(enrollment), [Enrollment.Status.WITHDRAWN])
        enrollment = services.move_to_step(enrollment, final, self.staff)
        self.assertEqual(services.ending_choices(enrollment), [Enrollment.Status.COMPLETED, Enrollment.Status.WITHDRAWN])
        enrollment = services.set_status(enrollment, Enrollment.Status.COMPLETED, self.staff)
        self.assertIsNotNone(enrollment.ended_at)

    def test_withdrawn_ends_and_dropped_needs_a_flow_rule(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        with self.assertRaisesMessage(ValidationError, "can't be dropped"):
            services.set_status(enrollment, Enrollment.Status.DROPPED, self.staff)
        enrollment = services.set_status(enrollment, Enrollment.Status.WITHDRAWN, self.staff)
        self.assertIsNotNone(enrollment.ended_at)

    def test_ended_can_change_how_it_ended_but_not_go_back(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff, step=self.final_step())
        enrollment = services.set_status(enrollment, Enrollment.Status.COMPLETED, self.staff)
        ended_at = enrollment.ended_at
        with self.assertRaisesMessage(ValidationError, "Reopen it first"):
            services.set_status(enrollment, Enrollment.Status.ACTIVE, self.staff)
        self.assertEqual(services.ending_choices(enrollment), [Enrollment.Status.WITHDRAWN])
        enrollment = services.set_status(enrollment, Enrollment.Status.WITHDRAWN, self.staff)
        self.assertEqual((enrollment.status, enrollment.ended_at), (Enrollment.Status.WITHDRAWN, ended_at))
        change = enrollment.activities.filter(kind="status_change").first()
        self.assertEqual((change.from_value, change.to_value), ("Completed", "Withdrawn"))

    def test_reopen(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        enrollment = services.set_status(enrollment, Enrollment.Status.WITHDRAWN, self.staff)
        enrollment = services.reopen(enrollment, self.staff)
        self.assertEqual((enrollment.status, enrollment.ended_at), (Enrollment.Status.ACTIVE, None))
        change = enrollment.activities.filter(kind="status_change").first()
        self.assertEqual((change.text, change.from_value, change.to_value, change.actor), ("Reopened", "Withdrawn", "Active", self.staff))
        services.reopen(enrollment, self.staff)
        self.assertEqual(enrollment.activities.filter(kind="status_change").count(), 2)

    def test_reopen_refused_after_enrolling_again(self):
        first = services.set_status(services.enroll(self.person, self.job_search, self.staff), "withdrawn", self.staff)
        services.enroll(self.person, self.job_search, self.staff)
        with self.assertRaisesMessage(services.AlreadyEnrolled, "already has an open Resume & Job Search enrollment"):
            services.reopen(first, self.staff)
        first.refresh_from_db()
        self.assertTrue(first.is_ended)

    def test_unknown_status_refused(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        with self.assertRaises(ValueError):
            services.set_status(enrollment, "lost", self.staff)


class NotesTest(PipelineTestCase):
    def test_add_note_and_contact_kinds(self):
        enrollment = services.enroll(self.person, self.job_search, self.staff)
        services.add_note(self.person, self.staff, "Left a voicemail", kind=Activity.Kind.PHONE, enrollment=enrollment)
        note = services.add_note(self.person, self.staff, "  Prefers email  ")
        self.assertEqual((note.text, note.kind, note.enrollment), ("Prefers email", "note", None))

    def test_system_kinds_and_empty_text_refused(self):
        with self.assertRaises(ValidationError):
            services.add_note(self.person, self.staff, "text", kind=Activity.Kind.STEP_CHANGE)
        with self.assertRaises(ValidationError):
            services.add_note(self.person, self.staff, "   ")

    def test_enrollment_must_belong_to_person(self):
        other = make_user("other@example.com")
        enrollment = services.enroll(other, self.job_search, self.staff)
        with self.assertRaises(ValidationError):
            services.add_note(self.person, self.staff, "text", enrollment=enrollment)

    def test_document_opened_is_recorded(self):
        services.record_document_opened(self.person, self.reviewer, "DD214")
        entry = Activity.objects.get(person=self.person)
        self.assertEqual((entry.kind, entry.text, entry.actor), ("document_opened", "DD214", self.reviewer))


class CompleteTriageTest(PipelineTestCase):
    def test_enrolls_in_flows_and_completes_intake(self):
        intake = services.enroll(self.person, self.intake, self.staff, step=self.triage)
        services.enroll(self.person, self.boot_camp, self.staff)
        created = services.complete_triage(intake, [self.job_search, self.boot_camp, self.intake], self.staff)
        self.assertEqual([e.flow for e in created], [self.job_search])
        intake.refresh_from_db()
        self.assertEqual(intake.status, Enrollment.Status.COMPLETED)
        self.assertEqual(
            set(Enrollment.objects.filter(person=self.person, ended_at__isnull=True).values_list("flow__slug", flat=True)),
            {"test-job-search", "test-boot-camp"},
        )

    def test_gated_step_blocks_triage_without_permission(self):
        intake = services.enroll(self.person, self.intake, self.staff)
        with self.assertRaises(PermissionDenied):
            services.complete_triage(intake, [self.job_search], self.staff)
        self.assertFalse(Enrollment.objects.filter(person=self.person, flow=self.job_search).exists())


class NextStepTest(PipelineTestCase):
    def test_next_step_crosses_phases_and_ends_with_none(self):
        self.assertEqual(self.first_email.next_step(), self.job_list)
        self.assertIsNone(self.job_list.next_step())
        self.assertEqual(self.verify.next_step(), self.triage)
