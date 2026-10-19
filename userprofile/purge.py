"""Legacy accounts from the old signup flow, which created a User as soon as an
email was entered (signup redesign Step 7). Used by purge_legacy_unverified_users."""
from allauth.account.adapter import get_adapter
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.db.models import Q

from .models import PendingSignup
from .signup import signup_link


def legacy_unverified_users(before):
    """Non-staff users joined before `before` with no password, no verified email,
    no finished onboarding and no cold_apply Participant."""
    return (
        User.objects.filter(is_staff=False, is_superuser=False, date_joined__lt=before)
        .filter(Q(password="") | Q(password__startswith=UNUSABLE_PASSWORD_PREFIX))
        .exclude(emailaddress__verified=True)
        .exclude(profile__is_onboarded=True)
        .exclude(participant__isnull=False)
        .distinct()
        .order_by("date_joined")
    )


def invite_and_delete(user):
    """Email a new signup link, then delete the account (the link only works once
    the account is gone). If sending raises, the account is kept."""
    email = user.email.strip().lower()
    if not email:
        user.delete()  # nobody to invite
        return
    PendingSignup.objects.filter(email=email).delete()
    pending = PendingSignup.objects.create(email=email)
    context = {"email": email, "signup_url": signup_link(pending), "current_site": get_current_site(None)}
    try:
        get_adapter().send_mail("account/email/signup_invite", email, context)
    except Exception:
        pending.delete()
        raise
    user.delete()
