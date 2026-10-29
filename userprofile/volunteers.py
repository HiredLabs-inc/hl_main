"""Volunteer invites and the volunteer home (docs/designs/in-progress/volunteer-logins.md §3.3-3.4).

1. invites_view (/staff/volunteers/): staff see the volunteers and pending
   invites, and invite someone by email, choosing the groups they get.
2. accept_view, the emailed link: a new email sets a password and gets an
   account; an existing account logs in and accepts. Either way the user joins
   Volunteers and the invite's groups, and skips onboarding.
3. home_view (/volunteer/home/): where volunteers land after logging in.
"""
import logging
import smtplib
from datetime import timedelta

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from django import forms
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import Group, User
from django.contrib.sites.shortcuts import get_current_site
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from pipeline.guards import can_work_lead_flows
from pipeline.models import Flow

from .guards import VOLUNTEERS_GROUP, is_participant, is_volunteer, staff_required
from .models import Profile, VolunteerInvite
from .signup import LINK_MAX_AGE, SEND_ERROR, absolute_url, read_token

logger = logging.getLogger(__name__)

TOKEN_SALT = "userprofile.volunteer_invite"
# Volunteers is always added; Staff means employee powers, and Veteran reviewers
# needs is_staff to do anything (guards.can_review_veteran_status)
NOT_OFFERED = [VOLUNTEERS_GROUP, "Staff", "Veteran reviewers"]


def account_for(email):
    """The account using email, as its login email or any of its addresses"""
    return User.objects.filter(Q(email__iexact=email) | Q(emailaddress__email__iexact=email)).distinct().first()


class VolunteerInviteForm(forms.Form):
    email = forms.EmailField(max_length=150)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Choose at least one group."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["groups"].queryset = Group.objects.exclude(name__in=NOT_OFFERED).order_by("name")
        for name in ("email", "first_name", "last_name"):
            self.fields[name].widget.attrs["class"] = "staff-field w-full"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        account = account_for(email)
        if account is not None and account.is_staff:
            raise forms.ValidationError("That's a staff account.")
        if account is not None and is_volunteer(account):
            raise forms.ValidationError("They're already a volunteer. Change their groups in Django admin.")
        return email


def make_token(invite):
    # The row id ties the link to this invite, so revoking it stops the link
    return signing.dumps({"id": invite.pk, "email": invite.email}, salt=TOKEN_SALT)


def invite_link(invite, request=None):
    return absolute_url(reverse("volunteer_invite_accept", args=[make_token(invite)]), request)


def send_invite(request, invite):
    """Email the invite link. Returns an error message for staff, or None."""
    context = {
        "invite": invite,
        "invite_url": invite_link(invite, request),
        "existing": account_for(invite.email) is not None,
        "inviter": request.user.get_full_name() or request.user.email,
        "current_site": get_current_site(request),
    }
    try:
        get_adapter(request).send_mail("account/email/volunteer_invite", invite.email, context)
    except (smtplib.SMTPException, OSError):
        logger.exception("Volunteer invite to %s failed", invite.email)
        return SEND_ERROR
    invite.last_sent_at = timezone.now()
    invite.save(update_fields=["last_sent_at"])
    return None


@staff_required
def invites_view(request):
    form = VolunteerInviteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            # Inviting an email again replaces its pending invite
            invite = VolunteerInvite.objects.filter(email=data["email"], accepted_at__isnull=True).first()
            invite = invite or VolunteerInvite(email=data["email"])
            invite.first_name, invite.last_name, invite.invited_by = data["first_name"], data["last_name"], request.user
            invite.save()
            invite.groups.set(data["groups"])
        error = send_invite(request, invite)
        if error:
            messages.error(request, f"The invite for {invite.email} is saved, but: {error}")
        else:
            messages.success(request, f"Invited {invite.email}.")
        return redirect("staff_volunteers")

    expired_before = timezone.now() - timedelta(seconds=LINK_MAX_AGE)
    invites = list(
        VolunteerInvite.objects.filter(accepted_at__isnull=True)
        .select_related("invited_by")
        .prefetch_related("groups")
        .order_by("-created_at")
    )
    for invite in invites:
        invite.expired = invite.last_sent_at is not None and invite.last_sent_at < expired_before
    volunteers = (
        User.objects.filter(groups__name=VOLUNTEERS_GROUP)
        .select_related("profile")
        .prefetch_related("groups")
        .order_by("-is_active", "first_name", "last_name", "email")
    )
    context = {"form": form, "invites": invites, "volunteers": volunteers, "volunteers_group": VOLUNTEERS_GROUP}
    return render(request, "userprofile/volunteers/invites.html", context)


@staff_required
@require_POST
def invite_action_view(request, pk, action):
    invite = get_object_or_404(VolunteerInvite, pk=pk, accepted_at__isnull=True)
    if action == "resend":
        error = send_invite(request, invite)
        if error:
            messages.error(request, error)
        else:
            messages.success(request, f"Sent a new invite link to {invite.email}.")
    elif action == "revoke":
        invite.delete()
        messages.success(request, f"Revoked the invite for {invite.email}. Its link no longer works.")
    else:
        raise Http404
    return redirect("staff_volunteers")


def _invalid(request, **context):
    return render(request, "account/volunteer_invite_invalid.html", context)


def _locked(invite):
    """Re-read a pending invite under a row lock, so a double submit can't accept it twice"""
    return VolunteerInvite.objects.select_for_update().filter(pk=invite.pk, accepted_at__isnull=True).first()


def _join(user, invite):
    user.groups.add(Group.objects.get(name=VOLUNTEERS_GROUP), *invite.groups.all())
    invite.accepted_at = timezone.now()
    invite.user = user
    invite.save(update_fields=["accepted_at", "user"])


def accept_view(request, token):
    payload, expired = read_token(token, salt=TOKEN_SALT)
    if payload is None or expired:
        return _invalid(request, expired=expired)
    invite = VolunteerInvite.objects.filter(pk=payload.get("id"), email=payload.get("email")).first()
    if invite is None:
        # Revoked by staff
        return _invalid(request)
    if invite.accepted_at:
        return _invalid(request, used=True)
    account = account_for(invite.email)
    if account is None:
        return _accept_new(request, invite)
    return _accept_existing(request, invite, account)


def _accept_new(request, invite):
    user = User(username=invite.email, email=invite.email, first_name=invite.first_name, last_name=invite.last_name)
    form = SetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = _locked(invite)
            if locked is None or account_for(invite.email):
                return _invalid(request, used=True)
            form.save()
            EmailAddress.objects.create(user=user, email=invite.email, verified=True, primary=True)
            _join(user, locked)
        login(request, user, backend="allauth.account.auth_backends.AuthenticationBackend")
        return redirect("volunteer_home")
    return render(request, "account/volunteer_invite.html", {"invite": invite, "form": form, "mode": "new"})


def _accept_existing(request, invite, account):
    context = {"invite": invite}
    if not request.user.is_authenticated:
        context["mode"] = "log_in"
        context["login_url"] = reverse("account_login") + "?" + urlencode({"next": request.path})
    elif request.user != account:
        context["mode"] = "wrong_account"
    elif request.method == "POST":
        with transaction.atomic():
            locked = _locked(invite)
            if locked is None:
                return _invalid(request, used=True)
            _join(account, locked)
        messages.success(request, "You're now a volunteer.")
        return redirect("volunteer_home")
    else:
        context["mode"] = "confirm"
    return render(request, "account/volunteer_invite.html", context)


@login_required
def home_view(request):
    """Cards for the tools the volunteer has, and their own job search if they
    want one (docs/designs/in-progress/volunteer-logins.md §3.2-3.3)"""
    user = request.user
    if not is_volunteer(user):
        return redirect("userprofile:user_home")
    lead_flows = Flow.objects.filter(active=True, subject=Flow.Subject.LEAD) if can_work_lead_flows(user) else []
    context = {
        "lead_flows": lead_flows,
        "participant": is_participant(user),
        "onboarding_started": Profile.objects.filter(user=user).exists(),
    }
    return render(request, "userprofile/volunteers/home.html", context)
