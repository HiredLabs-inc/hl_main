"""Volunteer accounts: invites, the volunteer home, and volunteers left out of
the participant lists (docs/designs/in-progress/volunteer-logins.md §3.1-3.4)."""
from datetime import datetime, timezone as dt_timezone
from unittest import mock

from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group, Permission, User
from django.core import mail
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from cold_apply.models import Participant
from pipeline.models import Enrollment
from userprofile import purge, reminders, volunteers
from userprofile.models import Profile, VolunteerInvite

from .test_onboarding import PASSWORD, verified_user
from .test_service_doc import MEDIA_ROOT, reviewer

INVITES = reverse("staff_volunteers")
HOME = reverse("volunteer_home")


def volunteer(email="val@example.com", groups=("Agents",), **kwargs):
    user = verified_user(email, **kwargs)
    user.groups.add(Group.objects.get(name="Volunteers"), *Group.objects.filter(name__in=groups))
    return user


class GroupsTest(TestCase):
    def test_volunteers_group_marks_the_role_only(self):
        self.assertFalse(Group.objects.get(name="Volunteers").permissions.exists())

    def test_agents_group_works_the_lead_flows(self):
        self.assertTrue(volunteer().has_perm("pipeline.work_lead_flows"))


class HomeTest(TestCase):
    def setUp(self):
        self.val = volunteer()
        self.client.force_login(self.val)

    def test_login_lands_on_the_volunteer_home(self):
        self.assertRedirects(self.client.get(reverse("userprofile:user_home")), HOME)

    def test_cards_for_the_tools_they_have(self):
        response = self.client.get(HOME)
        self.assertContains(response, reverse("hlagents:index"))
        self.assertContains(response, f"{reverse('staff')}?tab=funding")
        self.assertContains(response, "Get job search help")
        self.assertNotContains(response, reverse("staff_people"))

    def test_no_tools(self):
        self.client.force_login(volunteer("new@example.com", groups=()))
        response = self.client.get(HOME)
        self.assertContains(response, "You don't have access to any tools yet")
        self.assertNotContains(response, f"{reverse('staff')}?tab=funding")

    def test_can_start_onboarding_and_become_a_participant(self):
        self.client.get(reverse("userprofile:onboarding_view"))
        self.assertContains(self.client.get(HOME), "Continue onboarding")
        self.assertNotIn(self.val, reminders.unfinished_users())
        Profile.objects.get(user=self.val).handle_onboard_complete()
        self.assertTrue(Participant.objects.filter(user=self.val).exists())
        self.assertTrue(Enrollment.objects.filter(person=self.val, flow__slug="intake").exists())
        response = self.client.get(HOME)
        self.assertContains(response, "Your job search")
        self.assertContains(response, reverse("userprofile:profile_view"))
        # Still a volunteer first
        self.assertRedirects(self.client.get(reverse("userprofile:user_home")), HOME)

    def test_others_are_sent_home(self):
        self.client.force_login(verified_user("vet@example.com"))
        self.assertRedirects(self.client.get(HOME), reverse("userprofile:user_home"), target_status_code=302)

    def test_staff_only_pages_are_refused(self):
        person = verified_user("vet@example.com")
        for url in [
            reverse("staff_people"),
            reverse("staff_person", args=[person.pk]),
            reverse("stuck_signups"),
            reverse("staff_flows"),
            INVITES,
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)


@override_settings(MEDIA_ROOT=MEDIA_ROOT, GS_BUCKET_NAME="test-bucket")
class ServiceDocTest(TestCase):
    def test_volunteer_never_opens_a_dd214_even_as_a_reviewer(self):
        vet = verified_user("vet@example.com")
        Profile.objects.create(user=vet).service_doc.save("dd214.pdf", ContentFile(b"%PDF-1.4"))
        val = volunteer(groups=("Agents", "Veteran reviewers"))
        self.assertTrue(val.has_perm("userprofile.review_veteran_status"))
        self.client.force_login(val)
        self.assertEqual(self.client.get(reverse("service_doc", args=[vet.pk])).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("userprofile:veteran_status_update_view", args=[vet.pk])).status_code, 403
        )


class ParticipantListsTest(TestCase):
    def setUp(self):
        self.val = volunteer()
        Profile.objects.create(user=self.val)  # started onboarding, didn't finish
        self.alum = volunteer("alum@example.com")
        Profile.objects.create(user=self.alum, is_onboarded=True)
        self.vet = verified_user("vet@example.com")
        Profile.objects.create(user=self.vet)

    def test_people_shows_participant_volunteers_only(self):
        self.client.force_login(verified_user("staff@example.com", is_staff=True))
        response = self.client.get(reverse("staff_people"))
        shown = list(response.context["page"].object_list)
        self.assertIn(self.alum, shown)
        self.assertIn(self.vet, shown)
        self.assertNotIn(self.val, shown)
        self.assertContains(response, ">Volunteer</span>", count=1)

    def test_no_onboarding_reminders_for_volunteers(self):
        self.assertEqual(list(reminders.unfinished_users()), [self.vet])

    def test_volunteers_are_never_purged(self):
        val = volunteer("legacy@example.com")
        EmailAddress.objects.filter(user=val).update(verified=False)
        val.set_unusable_password()
        val.save()
        self.assertNotIn(val, purge.legacy_unverified_users(datetime(2100, 1, 1, tzinfo=dt_timezone.utc)))


class InviteTestCase(TestCase):
    def setUp(self):
        self.staff = verified_user("staff@example.com", is_staff=True, first_name="Sam", last_name="Staff")
        self.agents = Group.objects.get(name="Agents")
        self.client.force_login(self.staff)

    def invite(self, email="new@example.com", groups=None, **data):
        groups = [self.agents.pk] if groups is None else groups
        return self.client.post(INVITES, {"email": email, "first_name": "Nia", "last_name": "New", "groups": groups, **data})

    def link(self, index=-1):
        body = mail.outbox[index].body
        start = body.index("http://testserver/accounts/volunteer-invite/")
        return body[start:].split()[0].removeprefix("http://testserver")


class InviteTest(InviteTestCase):
    def test_staff_only(self):
        self.client.force_login(volunteer())
        self.assertEqual(self.client.get(INVITES).status_code, 403)
        self.client.logout()
        self.assertIn(reverse("account_login"), self.client.get(INVITES)["Location"])

    def test_groups_offered(self):
        Group.objects.create(name="Staff")
        offered = set(self.client.get(INVITES).context["form"].fields["groups"].queryset.values_list("name", flat=True))
        self.assertIn("Agents", offered)
        self.assertFalse(offered & {"Volunteers", "Staff", "Veteran reviewers"})
        reviewers = Group.objects.get(name="Veteran reviewers")
        self.assertFormError(self.invite(groups=[reviewers.pk]).context["form"], "groups", [
            f"Select a valid choice. {reviewers.pk} is not one of the available choices."
        ])

    def test_a_group_is_required(self):
        response = self.invite(groups=[])
        self.assertFormError(response.context["form"], "groups", ["Choose at least one group."])
        self.assertFalse(VolunteerInvite.objects.exists())

    def test_sends_an_invite(self):
        response = self.invite(email="New@Example.com")
        self.assertRedirects(response, INVITES)
        invite = VolunteerInvite.objects.get()
        self.assertEqual((invite.email, invite.invited_by, list(invite.groups.all())), ("new@example.com", self.staff, [self.agents]))
        self.assertIsNotNone(invite.last_sent_at)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])
        self.assertIn("Sam Staff invited you to volunteer", mail.outbox[0].body)
        self.assertIn("choose a password", mail.outbox[0].body)
        self.assertContains(self.client.get(INVITES), "new@example.com")

    def test_inviting_again_replaces_the_pending_invite(self):
        self.invite()
        other = Group.objects.create(name="Grant writers")
        self.invite(groups=[other.pk])
        invite = VolunteerInvite.objects.get()
        self.assertEqual(list(invite.groups.all()), [other])
        self.assertEqual(len(mail.outbox), 2)

    def test_staff_and_existing_volunteers_are_refused(self):
        volunteer("val@example.com")
        for email, error in [("staff@example.com", "staff account"), ("val@example.com", "already a volunteer")]:
            with self.subTest(email=email):
                self.assertIn(error, self.invite(email=email).context["form"].errors["email"][0])

    def test_send_failure_keeps_the_invite(self):
        with mock.patch("allauth.account.adapter.DefaultAccountAdapter.send_mail", side_effect=OSError("down")):
            response = self.invite()
        self.assertRedirects(response, INVITES)
        self.assertIsNone(VolunteerInvite.objects.get().last_sent_at)

    def test_resend_and_revoke(self):
        self.invite()
        invite = VolunteerInvite.objects.get()
        first_link = self.link()
        self.client.post(reverse("volunteer_invite_action", args=[invite.pk, "resend"]))
        self.assertEqual(len(mail.outbox), 2)
        self.client.post(reverse("volunteer_invite_action", args=[invite.pk, "revoke"]))
        self.assertFalse(VolunteerInvite.objects.exists())
        self.client.logout()
        for link in (first_link, self.link()):
            self.assertContains(self.client.get(link), "This Invite Doesn't Work")

    def test_unknown_action(self):
        self.invite()
        invite = VolunteerInvite.objects.get()
        self.assertEqual(self.client.post(reverse("volunteer_invite_action", args=[invite.pk, "nope"])).status_code, 404)


class AcceptNewTest(InviteTestCase):
    def setUp(self):
        super().setUp()
        self.invite()
        self.url = self.link()
        self.client.logout()

    def accept(self):
        return self.client.post(self.url, {"new_password1": PASSWORD, "new_password2": PASSWORD})

    def test_creates_a_verified_volunteer_and_logs_in(self):
        self.assertContains(self.client.get(self.url), "Create my account")
        self.assertRedirects(self.accept(), HOME)
        user = User.objects.get(email="new@example.com")
        self.assertEqual((user.first_name, user.last_name, user.is_staff), ("Nia", "New", False))
        self.assertTrue(EmailAddress.objects.get(user=user).verified)
        self.assertEqual(set(user.groups.values_list("name", flat=True)), {"Volunteers", "Agents"})
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        invite = VolunteerInvite.objects.get()
        self.assertEqual(invite.user, user)
        self.assertIsNotNone(invite.accepted_at)
        # No onboarding, Participant or Intake
        self.assertFalse(Profile.objects.filter(user=user).exists())
        self.assertFalse(Participant.objects.filter(user=user).exists())
        self.assertFalse(Enrollment.objects.filter(person=user).exists())

    def test_link_works_once(self):
        self.accept()
        self.client.logout()
        self.assertContains(self.client.get(self.url), "This Invite Was Already Accepted")
        self.assertContains(self.accept(), "This Invite Was Already Accepted")
        self.assertEqual(User.objects.filter(email="new@example.com").count(), 1)

    def test_expired_and_bad_links(self):
        with mock.patch("userprofile.signup.LINK_MAX_AGE", -1):
            self.assertContains(self.client.get(self.url), "This Invite Has Expired")
        self.assertContains(self.client.get(self.url[:-3] + "xyz/"), "This Invite Doesn't Work")

    def test_signup_tokens_are_not_invites(self):
        from userprofile import signup
        from userprofile.models import PendingSignup

        token = signup.make_token(PendingSignup.objects.create(email="new@example.com"))
        response = self.client.get(reverse("volunteer_invite_accept", args=[token]))
        self.assertContains(response, "This Invite Doesn't Work")

    def test_weak_password(self):
        response = self.client.post(self.url, {"new_password1": "short", "new_password2": "short"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())


class AcceptExistingTest(InviteTestCase):
    def setUp(self):
        super().setUp()
        self.alum = verified_user("alum@example.com")
        self.profile = Profile.objects.create(user=self.alum, is_onboarded=True)
        self.invite(email="alum@example.com")
        self.url = self.link()
        self.client.logout()

    def test_email_says_log_in(self):
        self.assertIn("already have an account", mail.outbox[0].body)

    def test_log_in_first(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["mode"], "log_in")
        self.assertContains(response, f"{reverse('account_login')}?next=")

    def test_wrong_account(self):
        self.client.force_login(verified_user("vet@example.com"))
        self.assertEqual(self.client.get(self.url).context["mode"], "wrong_account")
        self.assertEqual(self.client.post(self.url).context["mode"], "wrong_account")
        self.assertFalse(self.alum.groups.exists())

    def test_accept_adds_the_groups_and_keeps_participant_data(self):
        self.client.force_login(self.alum)
        self.assertEqual(self.client.get(self.url).context["mode"], "confirm")
        self.assertFalse(self.alum.groups.exists())
        self.assertRedirects(self.client.post(self.url), HOME)
        self.assertEqual(set(self.alum.groups.values_list("name", flat=True)), {"Volunteers", "Agents"})
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_onboarded)
        self.assertTrue(self.alum.check_password(PASSWORD))
        self.assertContains(self.client.get(self.url), "This Invite Was Already Accepted")

    def test_found_by_any_of_their_addresses(self):
        EmailAddress.objects.create(user=self.alum, email="old@example.com")
        self.assertEqual(volunteers.account_for("OLD@example.com"), self.alum)


class NavTest(TestCase):
    def test_volunteer_nav(self):
        self.client.force_login(volunteer())
        response = self.client.get(HOME)
        self.assertContains(response, ">Leads</a>")
        self.assertContains(response, ">Agents</a>")
        for hidden in (reverse("staff_people"), reverse("stuck_signups"), reverse("staff_flows"), INVITES, reverse("admin:index")):
            self.assertNotContains(response, f'href="{hidden}"')

    def test_release_notes_follow_the_permission(self):
        """BUG-042: plain staff no longer see release links they can't open"""
        from releases.models import App

        app = App.objects.create(name="hl_main")
        link = reverse("releases:index", args=[app.pk])
        staff = verified_user("staff@example.com", is_staff=True)
        self.client.force_login(staff)
        self.assertNotContains(self.client.get(reverse("staff_flows")), link)
        staff.user_permissions.add(Permission.objects.filter(content_type__app_label="releases").first())
        self.client.force_login(User.objects.get(pk=staff.pk))
        self.assertContains(self.client.get(reverse("staff_flows")), link)

    def test_staff_get_the_volunteers_page(self):
        self.client.force_login(verified_user("staff@example.com", is_staff=True))
        self.assertContains(self.client.get(reverse("staff_flows")), f'href="{INVITES}"')
