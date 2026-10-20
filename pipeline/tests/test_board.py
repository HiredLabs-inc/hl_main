import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from pipeline import dashboard, services
from pipeline.models import Enrollment, Flow, Phase, Step

from .test_dashboard import URL, DashboardTestCase, person

JOB_SEARCH = "resume-job-search"


def add_steps(flow, count):
    """Fresh databases give each flow one step; add count more, two to a new phase,
    the first of them owned by the participant"""
    for i in range(count):
        if i % 2 == 0:
            phase = Phase.objects.create(flow=flow, title=f"Phase {i // 2 + 2}", order=i // 2 + 1)
        owner = Step.Owner.PARTICIPANT if i == 0 else Step.Owner.HIRED_LABS
        Step.objects.create(phase=phase, title=f"Step {i + 2}", order=i % 2, owner=owner)


def board(response):
    """{step title: [emails]} for the columns a board response shows"""
    return {
        column.step.title: [card.person.email for card in column.cards]
        for group in response.context["phases"]
        for column in group.columns
    }


def column(response, step):
    return next(c for group in response.context["phases"] for c in group.columns if c.step == step)


class BoardTestCase(DashboardTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        add_steps(cls.job_search, 3)

    def get(self, headers=None, **params):
        return self.client.get(URL, {"tab": JOB_SEARCH, "view": "board", **params}, **(headers or {}))


class ViewSwitchTest(BoardTestCase):
    def test_new_session_opens_on_the_table(self):
        response = self.client.get(URL, {"tab": JOB_SEARCH})
        self.assertEqual(response.context["view"], "table")
        self.assertTemplateUsed(response, "pipeline/partials/enrollment_table.html")
        self.assertContains(response, "view=board")

    def test_board_and_session_remembers_it(self):
        self.assertTemplateUsed(self.get(), "pipeline/partials/board.html")
        response = self.client.get(URL, {"tab": "boot-camp"})
        self.assertEqual(response.context["view"], "board")
        self.client.get(URL, {"tab": JOB_SEARCH, "view": "table"})
        self.assertEqual(self.client.get(URL, {"tab": JOB_SEARCH}).context["view"], "table")

    def test_filter_form_carries_the_view(self):
        self.assertContains(self.get(), 'name="view" value="board"')

    def test_no_board_on_intake_or_mixed_tabs(self):
        self.get()
        for tab in ("intake", "mine", "all"):
            with self.subTest(tab=tab):
                response = self.client.get(URL, {"tab": tab, "view": "board"})
                self.assertEqual(response.context["view"], "table")
                self.assertNotContains(response, "view=board")
        # Visiting them doesn't forget the choice
        self.assertEqual(self.client.get(URL, {"tab": JOB_SEARCH}).context["view"], "board")

    def test_htmx_gets_only_the_board(self):
        response = self.get(headers={"HTTP_HX_REQUEST": "true"})
        self.assertTemplateUsed(response, "pipeline/partials/board.html")
        self.assertTemplateNotUsed(response, "pipeline/dashboard.html")


class BoardTest(BoardTestCase):
    def test_columns_for_every_step_with_open_enrollments_only(self):
        response = self.get()
        columns = board(response)
        steps = list(Step.objects.filter(phase__flow=self.job_search))
        self.assertEqual(list(columns), [step.title for step in steps])
        self.assertEqual(
            sorted(columns[steps[0].title]), ["loose@example.com", "mine@example.com", "theirs@example.com"]
        )
        self.assertNotContains(response, "done@example.com")

    def test_oldest_in_step_first(self):
        Enrollment.objects.filter(pk=self.loose.pk).update(step_entered_at=timezone.now() - timedelta(days=40))
        first = self.job_search.first_step().title
        self.assertEqual(board(self.get())[first], ["loose@example.com", "theirs@example.com", "mine@example.com"])

    def test_cards_grouped_by_step(self):
        second = Step.objects.filter(phase__flow=self.job_search)[1]
        services.move_to_step(self.mine, second, self.staff)
        self.assertEqual(board(self.get())[second.title], ["mine@example.com"])

    def test_phone_starts_on_the_first_step_with_cards(self):
        self.assertEqual(self.get().context["board_start"], self.job_search.first_step().pk)
        second = Step.objects.filter(phase__flow=self.job_search)[1]
        Enrollment.objects.filter(flow=self.job_search).update(current_step=second)
        self.assertEqual(self.get().context["board_start"], second.pk)
        self.assertEqual(dashboard.board_start([]), None)

    def test_phases_and_counts(self):
        response = self.get()
        groups = response.context["phases"]
        self.assertEqual([g.phase for g in groups], list(self.job_search.phases.all()))
        self.assertEqual(groups[0].count, 3)
        self.assertContains(response, "3 people")

    def test_empty_steps_collapse(self):
        response = self.get()
        second = Step.objects.filter(phase__flow=self.job_search)[1]
        self.assertContains(response, f"Show {second.title} (nobody on this step)")
        self.assertNotContains(response, f"Show {self.job_search.first_step().title} (nobody")

    def test_participant_steps_are_labelled(self):
        response = self.get()
        step = Step.objects.get(phase__flow=self.job_search, title="Step 2")
        self.assertTrue(column(response, step).waiting_on_participant)
        self.assertContains(response, "Waiting on participant", count=1)

    def test_filters_hide_cards_but_not_columns(self):
        response = self.get(assignee="me")
        first = column(response, self.job_search.first_step())
        self.assertEqual([c.person.email for c in first.cards], ["mine@example.com"])
        self.assertEqual((first.count, first.open), (1, 3))
        self.assertEqual(len(board(response)), Step.objects.filter(phase__flow=self.job_search).count())

    def test_phase_filter_hides_other_phases(self):
        phase = self.job_search.phases.all()[1]
        groups = self.get(phase=phase.pk).context["phases"]
        self.assertEqual([g.phase for g in groups], [phase])

    def test_ended_status_filter_shows_nobody(self):
        self.assertEqual(sum(map(len, board(self.get(status="completed")).values())), 0)

    def test_invalid_filter_shows_error(self):
        self.assertContains(self.get(days="0"), "Some filters aren't valid")


class CardTest(BoardTestCase):
    def card(self, enrollment, response=None):
        response = response or self.get()
        step = Enrollment.objects.get(pk=enrollment.pk).current_step
        return next(c for c in column(response, step).cards if c.pk == enrollment.pk)

    def test_card_shows_assignee_days_and_badges(self):
        response = self.get()
        self.assertContains(response, f'id="card-{self.mine.pk}"')
        self.assertContains(response, "Assigned to Sam Staff")
        self.assertContains(response, "Unassigned")
        self.assertContains(response, "30d in step")
        self.assertContains(response, "DNC")
        self.assertContains(response, "Paused")
        self.assertEqual(self.card(self.mine, response).assignee_initials, "SS")

    def test_other_open_enrollments(self):
        services.enroll(self.mine.person, Flow.objects.get(slug="boot-camp"), None)
        self.assertContains(self.get(), "Also in Boot Camp")

    def test_last_activity_and_rejection_reason(self):
        services.add_note(self.mine.person, self.staff, "Called", kind="phone")
        services.set_status(self.theirs, Enrollment.Status.REJECTED, self.staff, reason="Unclear DD214")
        response = self.get()
        self.assertEqual(self.card(self.mine, response).last_activity_label, "Phone")
        self.assertEqual(self.card(self.theirs, response).last_activity_label, "Unclear DD214")
        services.add_note(self.theirs.person, self.staff, "Sent a reminder")
        self.assertEqual(self.card(self.theirs).last_activity_label, "Note")


class BigColumnTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("staff@example.com", is_staff=True)
        cls.flow = Flow.objects.get(slug=JOB_SEARCH)
        cls.step = cls.flow.first_step()
        now = timezone.now()
        for i in range(31):
            enrollment = services.enroll(person(f"p{i:02}@example.com", "P", f"{i:02}"), cls.flow, None)
            # p00 is the oldest
            Enrollment.objects.filter(pk=enrollment.pk).update(step_entered_at=now - timedelta(days=100 - i))
        services.set_status(Enrollment.objects.get(person__email="p30@example.com"), "paused", None)

    def setUp(self):
        self.client.force_login(self.staff)

    def test_first_page_and_compact_cards(self):
        response = self.client.get(URL, {"tab": JOB_SEARCH, "view": "board"})
        first = column(response, self.step)
        self.assertEqual((len(first.cards), first.count, first.more, first.compact), (25, 31, 6, True))
        self.assertEqual(first.cards[0].person.email, "p00@example.com")
        self.assertContains(response, "Show 6 more")
        self.assertContains(response, "Open all 31 in the table")

    def test_not_compact_at_thirty(self):
        url = URL + f"?tab={JOB_SEARCH}&view=board&status=active"
        self.assertFalse(column(self.client.get(url), self.step).compact)

    def column_url(self, step=None):
        return reverse("pipeline:board_column", args=[JOB_SEARCH, (step or self.step).pk])

    def test_show_more(self):
        response = self.client.get(self.column_url(), {"offset": 25})
        self.assertTemplateUsed(response, "pipeline/partials/board_cards.html")
        page = response.context["column"]
        self.assertEqual([c.person.email for c in page.cards][:1], ["p25@example.com"])
        self.assertEqual((len(page.cards), page.more), (6, 0))
        self.assertNotContains(response, "Show ")

    def test_show_more_keeps_filters(self):
        response = self.client.get(self.column_url(), {"offset": 0, "status": "paused", "tab": JOB_SEARCH})
        self.assertEqual([c.person.email for c in response.context["column"].cards], ["p30@example.com"])

    def test_column_endpoint_refuses_bad_requests(self):
        intake = Flow.objects.get(slug="intake")
        self.assertEqual(self.client.get(self.column_url(), {"days": "0"}).status_code, 400)
        other = reverse("pipeline:board_column", args=[JOB_SEARCH, intake.first_step().pk])
        self.assertEqual(self.client.get(other).status_code, 404)
        no_board = reverse("pipeline:board_column", args=["intake", intake.first_step().pk])
        self.assertEqual(self.client.get(no_board).status_code, 404)

    def test_column_endpoint_is_staff_only(self):
        self.client.logout()
        self.assertIn(reverse("account_login"), self.client.get(self.column_url())["Location"])
        self.client.force_login(User.objects.get(email="p00@example.com"))
        self.assertEqual(self.client.get(self.column_url()).status_code, 403)


class BoardQueryCountTest(TestCase):
    def test_queries_do_not_grow_with_cards(self):
        staff = User.objects.create_user("staff@example.com", is_staff=True)
        flow = Flow.objects.get(slug=JOB_SEARCH)
        add_steps(flow, 9)
        steps = list(Step.objects.filter(phase__flow=flow))
        other = Flow.objects.get(slug="boot-camp")
        self.client.force_login(staff)

        def queries_for(count):
            for i in range(Enrollment.objects.filter(flow=flow).count(), count):
                user = person(f"p{i}@example.com", "P", str(i))
                enrollment = services.enroll(user, flow, staff, step=steps[i % len(steps)], assignee=staff)
                services.add_note(user, staff, "hello", enrollment=enrollment)
                services.enroll(user, other, staff)
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(URL, {"tab": JOB_SEARCH, "view": "board"})
            self.assertEqual(sum(len(c.cards) for g in response.context["phases"] for c in g.columns), count)
            return len(queries)

        self.assertEqual(queries_for(5), queries_for(50))


class ColumnTest(TestCase):
    def test_paging_properties(self):
        step = Step(title="x")
        column = dashboard.Column(step, cards=list(range(25)), count=60, open=60, offset=25)
        self.assertEqual((column.next_offset, column.more, column.next_page), (50, 10, 10))
        self.assertTrue(column.compact)


class MoveCardTest(BoardTestCase):
    """The board's Move: pipeline:move with render=card"""

    def setUp(self):
        super().setUp()
        self.first, self.second, self.third, self.fourth = Step.objects.filter(phase__flow=self.job_search)

    def move(self, enrollment, step, from_step=None, page="", **headers):
        return self.client.post(
            reverse("pipeline:move", args=[enrollment.pk]),
            {"step": step.pk, "from_step": (from_step or enrollment.current_step).pk, "render": "card"},
            HTTP_HX_CURRENT_URL=f"http://testserver/staff/?tab={JOB_SEARCH}&view=board{page}",
            **headers,
        )

    def step_changes(self, enrollment):
        return enrollment.activities.filter(kind="step_change").count()

    def test_move_answers_with_the_card_and_counts(self):
        response = self.move(self.mine, self.third)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pipeline/partials/board_move.html")
        self.assertEqual(Enrollment.objects.get(pk=self.mine.pk).current_step, self.third)
        self.assertEqual(self.step_changes(self.mine), 1)
        self.assertEqual(response["HX-Board-Card"], "true")
        self.assertContains(response, f'id="card-{self.mine.pk}" data-board-card data-step="{self.third.pk}" data-board-moved')
        self.assertEqual(response.context["step_counts"], {self.first.pk: 2, self.third.pk: 1})
        self.assertEqual(response.context["phase_counts"], {self.first.phase_id: 2, self.third.phase_id: 1})
        self.assertContains(response, f'id="board-count-{self.third.pk}" hx-swap-oob="true"')
        self.assertContains(response, f'id="board-phase-count-{self.third.phase_id}" hx-swap-oob="true"')

    def test_counts_use_the_page_filters(self):
        response = self.move(self.mine, self.third, page="&assignee=unassigned")
        self.assertEqual(response.context["step_counts"], {self.first.pk: 1, self.third.pk: 0})

    def test_toast_offers_undo_and_undo_moves_back(self):
        toast = json.loads(self.move(self.mine, self.third)["HX-Trigger"])["toast"]
        self.assertEqual(toast["text"], "Moved Mia Mine to Step 3.")
        undo = toast["undo"]
        self.assertEqual(undo["card"], f"card-{self.mine.pk}")
        self.assertEqual(undo["values"], {"step": self.first.pk, "from_step": self.third.pk, "render": "card"})
        response = self.client.post(undo["url"], undo["values"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Enrollment.objects.get(pk=self.mine.pk).current_step, self.first)
        self.assertEqual(self.step_changes(self.mine), 2)

    def test_stale_board_is_409(self):
        services.move_to_step(self.mine, self.second, self.staff)
        response = self.move(self.mine, self.third, from_step=self.first)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Enrollment.objects.get(pk=self.mine.pk).current_step, self.second)
        self.assertEqual(self.step_changes(self.mine), 1)
        self.assertContains(response, "Sam Staff moved Mia to Step 2 just now.", status_code=409)
        self.assertContains(response, f'data-step="{self.second.pk}"', status_code=409)
        self.assertNotIn("toast", json.loads(response["HX-Trigger"]))

    def test_gated_step_is_403(self):
        self.first.required_permission = "userprofile.review_veteran_status"
        self.first.save()
        self.assertContains(self.get(), "Reviewer only")
        response = self.move(self.mine, self.third)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.step_changes(self.mine), 0)
        self.assertContains(response, "Only veteran reviewers can move people off Resume", status_code=403)

    def test_ended_enrollment_is_400_and_the_card_goes(self):
        done = Enrollment.objects.get(person__email="done@example.com")
        response = self.move(done, self.third)
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(response.context["enrollment"])
        self.assertNotContains(response, "data-board-card", status_code=400)
        self.assertEqual(json.loads(response["HX-Trigger"])["toast"]["text"], "This enrollment has ended.")
        self.assertEqual(self.step_changes(done), 0)

    def test_step_from_another_flow_is_400(self):
        response = self.move(self.mine, self.verify)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Choose a step in this flow.", status_code=400)

    def test_menu_lists_the_flow_steps(self):
        response = self.get()
        self.assertContains(response, f"Move {self.mine.person.get_full_name()}")
        self.assertContains(response, "Resume &amp; Job Search (current)", count=3)
        self.assertContains(response, '"from_step": "%d", "render": "card"' % self.first.pk)

    def test_table_refuses_a_stale_move(self):
        services.move_to_step(self.mine, self.second, self.other_staff)
        response = self.client.post(
            reverse("pipeline:move", args=[self.mine.pk]), {"step": self.third.pk, "from_step": self.first.pk}
        )
        self.assertEqual(response["HX-Reswap"], "none")
        self.assertIn("moved Mia to Step 2", json.loads(response["HX-Trigger"])["toast"]["text"])
        self.assertEqual(Enrollment.objects.get(pk=self.mine.pk).current_step, self.second)
