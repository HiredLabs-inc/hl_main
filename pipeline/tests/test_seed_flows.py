from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from pipeline.models import Activity, Enrollment, Flow, Step
from userprofile.models import Profile

from .old_pipeline import create_old_tables, seed

# Prod phases and steps from the Step 0 query (design doc §8), as (phase, order,
# active, [(step, order, owner)]). Several orders are tied, as in prod (BUG-031).
PROD = [
    ("Phase 1", 0, True, [("Send Initial Email", 0, "Hired Labs"), ("Fill out intake form", 1, "Participant"),
                          ("Intake Call", 2, "Hired Labs"), ("Conduct Intake Call", 3, "Hired Labs")]),
    ("Phase 2", 1, True, [("Create Initial Job List", 0, "Hired Labs"), ("Analyze keywords in job posts", 1, "Hired Labs"),
                          ("Write tailored bullets and overview", 2, "Hired Labs")]),
    ("Phase 3", 2, True, [("Send Initial Job and Resume Set", 0, "Hired Labs"), ("Give Feedback on Initial Packet", 2, "Participant"),
                          ("Review for Resume Service", 3, "Hired Labs"), ("Offer Resume & Job Search", 1, "Hired Labs")]),
    ("Phase 4", 3, True, [("Apply to Jobs", 0, "Hired Labs"), ("No Show", 1, "Hired Labs"),
                          ("Send Rejection Message", 1, "Hired Labs")]),
    ("Phase 5", 4, True, [("Send End-of-Process Comms", 0, "Hired Labs")]),
    ("Nurture", 0, False, [("Monthly Newsletter", 1, "Hired Labs"), ("Boot Camp Alumni", 0, "Hired Labs")]),
    ("Do Not Contact", 1, False, [("Do nothing", 0, "Hired Labs")]),
    ("Boot Camp On-boarding", 3, True, [("Send Commitment Form", 0, "Hired Labs"), ("Send Rejection Message", 0, "Hired Labs"),
                                        ("Send Waitlist 1 Message", 1, "Hired Labs"), ("Fill out Commitment Form", 2, "Participant")]),
    ("Boot Camp Wait List", 4, True, [("Priority Enrollment - Next Cycle", 0, "Hired Labs"), ("Make Way for Enlisted", 0, "Hired Labs")]),
    ("Applicants", 0, True, [("Verify Veteran Status", 0, "Hired Labs")]),
]


def titles(queryset):
    return list(queryset.values_list("title", flat=True))


class FreshDatabaseTest(TestCase):
    """The migration has already run on the empty test database"""

    def test_four_flows_each_with_a_step(self):
        self.assertEqual(
            list(Flow.objects.values_list("slug", flat=True)), ["intake", "resume-job-search", "boot-camp", "nurture"]
        )
        for flow in Flow.objects.all():
            self.assertIsNotNone(flow.first_step(), flow.slug)

    def test_intake_is_gated_verify_then_triage(self):
        steps = Step.objects.filter(phase__flow__slug="intake")
        self.assertEqual(titles(steps), ["Verify Veteran Status", "Triage"])
        self.assertEqual(steps[0].required_permission, "userprofile.review_veteran_status")
        self.assertEqual(steps[1].required_permission, "")


class SeedFromProdShapeTest(TestCase):
    """Each test recreates the old cold_apply tables; Postgres rolls the schema
    changes back with the test's transaction"""

    def setUp(self):
        self.old_apps = create_old_tables()
        self.OldPhase, self.OldStep, self.Participant, self.Interaction = (
            self.old_apps.get_model("cold_apply", name) for name in ("Phase", "Step", "Participant", "Interaction")
        )
        seed.unseed_flows(self.old_apps)
        self.old = {}
        for phase_title, phase_order, active, steps in PROD:
            phase = self.OldPhase.objects.create(title=phase_title, order=phase_order, active=active, start="s", end="e", result="r")
            for title, order, owner in steps:
                self.old[(phase_title, title)] = self.OldStep.objects.create(
                    phase=phase, title=title, order=order, owner=owner, description=f"About {title}"
                )
        self.staff = User.objects.create_user("staff@example.com", is_staff=True)

    def participant(self, email, phase=None, step=None, profile_dnc=None):
        user = User.objects.create_user(email)
        if profile_dnc is not None:
            Profile.objects.create(user=user, dnc=profile_dnc)
        return self.Participant.objects.create(user_id=user.pk, current_step=self.old[(phase, step)] if phase else None)

    def enrollment(self, participant):
        return Enrollment.objects.get(person_id=participant.user_id)

    def test_flow_structure_follows_prod_with_ties_ordered_by_id(self):
        seed.seed_flows(self.old_apps)
        self.assertEqual(
            titles(Step.objects.filter(phase__flow__slug="resume-job-search", phase__title="Phase 3")),
            ["Send Initial Job and Resume Set", "Offer Resume & Job Search",
             "Give Feedback on Initial Packet", "Review for Resume Service"],
        )
        self.assertEqual(
            list(Flow.objects.get(slug="resume-job-search").phases.values_list("title", "order")),
            [("Phase 1", 0), ("Phase 2", 1), ("Phase 3", 2), ("Phase 4", 3), ("Phase 5", 4)],
        )
        self.assertEqual(titles(Flow.objects.get(slug="boot-camp").phases), ["Boot Camp On-boarding", "Boot Camp Wait List"])
        self.assertEqual(titles(Step.objects.filter(phase__title="Phase 4")), ["Apply to Jobs"])
        self.assertEqual(
            titles(Step.objects.filter(phase__title="Boot Camp On-boarding")),
            ["Send Commitment Form", "Send Waitlist 1 Message", "Fill out Commitment Form"],
        )
        self.assertEqual(titles(Step.objects.filter(phase__flow__slug="nurture")), ["Boot Camp Alumni", "Nurture"])
        self.assertEqual(titles(Step.objects.filter(phase__flow__slug="intake")), ["Verify Veteran Status", "Triage"])
        self.assertFalse(Step.objects.filter(title__in=["Do nothing", "Monthly Newsletter"]).exists())
        self.assertEqual(
            list(Step.objects.filter(phase__title="Phase 3").values_list("order", flat=True)), [0, 1, 2, 3]
        )
        copied = Step.objects.get(title="Fill out intake form")
        self.assertEqual((copied.owner, copied.description), ("Participant", "About Fill out intake form"))
        phase = copied.phase
        self.assertEqual((phase.start, phase.end, phase.result), ("s", "e", "r"))

    def test_participants_get_one_enrollment_on_the_copied_step(self):
        job = self.participant("job@example.com", "Phase 2", "Create Initial Job List")
        camp = self.participant("camp@example.com", "Boot Camp Wait List", "Make Way for Enlisted")
        nurture = self.participant("nurture@example.com", "Nurture", "Monthly Newsletter")
        applicant = self.participant("new@example.com", "Applicants", "Verify Veteran Status")
        cases = [
            (job, "resume-job-search", "Create Initial Job List"),
            (camp, "boot-camp", "Make Way for Enlisted"),
            (nurture, "nurture", "Nurture"),
            (applicant, "intake", "Verify Veteran Status"),
        ]
        seed.seed_flows(self.old_apps)
        for participant, flow, step in cases:
            with self.subTest(participant=participant.user_id):
                enrollment = self.enrollment(participant)
                self.assertEqual((enrollment.flow.slug, enrollment.current_step.title), (flow, step))
                self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)
                self.assertEqual(enrollment.step_entered_at, participant.updated_at)
                self.assertEqual(enrollment.created_at, participant.created_at)
                activity = enrollment.activities.get()
                self.assertEqual((activity.kind, activity.to_value, activity.actor), ("enrolled", step, None))

    def test_do_not_contact_sets_dnc_without_enrollment(self):
        with_profile = self.participant("dnc@example.com", "Do Not Contact", "Do nothing", profile_dnc=False)
        without_profile = self.participant("dnc2@example.com", "Do Not Contact", "Do nothing")
        bystander = self.participant("ok@example.com", "Phase 1", "Send Initial Email", profile_dnc=False)
        seed.seed_flows(self.old_apps)
        for participant in (with_profile, without_profile):
            self.assertTrue(Profile.objects.get(user_id=participant.user_id).dnc)
            self.assertFalse(Enrollment.objects.filter(person_id=participant.user_id).exists())
            self.assertEqual(Activity.objects.get(person_id=participant.user_id).kind, "note")
        self.assertFalse(Profile.objects.get(user_id=bystander.user_id).dnc)

    def test_no_show_and_rejection_become_statuses_on_the_step_before(self):
        no_show = self.participant("noshow@example.com", "Phase 4", "No Show")
        rejected = self.participant("rejected@example.com", "Boot Camp On-boarding", "Send Rejection Message")
        seed.seed_flows(self.old_apps)
        enrollment = self.enrollment(no_show)
        self.assertEqual((enrollment.current_step.title, enrollment.status), ("Apply to Jobs", "no_show"))
        enrollment = self.enrollment(rejected)
        self.assertEqual((enrollment.current_step.title, enrollment.status), ("Send Commitment Form", "rejected"))
        change = enrollment.activities.get(kind="status_change")
        self.assertEqual((change.from_value, change.to_value), ("Active", "Rejected"))
        self.assertIn("Send Rejection Message", change.text)

    def test_participant_without_step_goes_to_triage(self):
        lost = self.participant("lost@example.com")
        seed.seed_flows(self.old_apps)
        enrollment = self.enrollment(lost)
        self.assertEqual((enrollment.flow.slug, enrollment.current_step.title), ("intake", "Triage"))

    def test_interactions_become_timeline_entries(self):
        participant = self.participant("talk@example.com", "Phase 1", "Intake Call")
        when = timezone.now() - timedelta(days=30)
        for kind, notes in (("PHONE", "Left voicemail"), ("OTHER", None)):
            interaction = self.Interaction.objects.create(
                user_id=self.staff.pk, participant=participant, interaction_type=kind, notes=notes
            )
            self.Interaction.objects.filter(pk=interaction.pk).update(created_at=when)
        seed.seed_flows(self.old_apps)
        entries = Activity.objects.filter(person_id=participant.user_id, enrollment=None).order_by("id")
        self.assertEqual(
            list(entries.values_list("kind", "text", "actor", "created_at")),
            [("phone", "Left voicemail", self.staff.pk, when), ("note", "", self.staff.pk, when)],
        )

    def test_unknown_phase_stops_the_migration(self):
        self.OldPhase.objects.create(title="Mystery", start="", end="", result="")
        with self.assertRaisesMessage(RuntimeError, "Mystery"):
            seed.seed_flows(self.old_apps)

    def test_unseed_removes_pipeline_rows_but_keeps_dnc(self):
        participant = self.participant("dnc@example.com", "Do Not Contact", "Do nothing", profile_dnc=False)
        self.participant("job@example.com", "Phase 2", "Create Initial Job List")
        seed.seed_flows(self.old_apps)
        seed.unseed_flows(self.old_apps)
        for model in (Flow, Step, Enrollment, Activity):
            self.assertFalse(model.objects.exists(), model.__name__)
        self.assertTrue(Profile.objects.get(user_id=participant.user_id).dnc)
