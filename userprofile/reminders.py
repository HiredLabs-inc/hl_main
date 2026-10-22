"""Reminder emails for people who stall during signup (run daily by the
send_signup_reminders command; staff can also send them from the Stuck signups page).

- PendingSignup whose link wasn't followed: one reminder, a day after the last email.
- User with an account who hasn't finished onboarding: reminders about 3 and 14
  days after joining. Accounts older than ONBOARDING_REMINDER_WINDOW get none
  (legacy accounts are handled by the purge in Step 7 of the signup redesign).
"""
import logging
from datetime import timedelta

from allauth.account.adapter import get_adapter
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import OnboardingReminder, PendingSignup
from .signup import absolute_url, signup_link

logger = logging.getLogger(__name__)

PENDING_REMINDER_AFTER = timedelta(hours=24)
PENDING_REMINDER_WINDOW = timedelta(days=30)
ONBOARDING_REMINDERS_AFTER = [timedelta(days=3), timedelta(days=14)]
ONBOARDING_REMINDER_GAP = timedelta(days=3)
ONBOARDING_REMINDER_WINDOW = timedelta(days=30)
# Signups never completed are deleted after this long (their links expired long before).
PENDING_EXPIRY = timedelta(days=30)


def expired_pending(now=None):
    now = now or timezone.now()
    return PendingSignup.objects.filter(completed_at__isnull=True, created_at__lt=now - PENDING_EXPIRY)


def unfinished_users():
    """Non-staff users with a verified email who haven't finished onboarding."""
    return (
        User.objects.filter(is_staff=False, is_active=True, emailaddress__verified=True)
        .filter(Q(profile__isnull=True) | Q(profile__is_onboarded=False))
        .distinct()
    )


def pending_due(now=None):
    now = now or timezone.now()
    return PendingSignup.objects.filter(
        completed_at__isnull=True,
        reminder_sent_at__isnull=True,
        send_count__gte=1,
        last_sent_at__lte=now - PENDING_REMINDER_AFTER,
        created_at__gte=now - PENDING_REMINDER_WINDOW,
    )


def users_due(now=None):
    now = now or timezone.now()
    due = []
    users = unfinished_users().filter(date_joined__gte=now - ONBOARDING_REMINDER_WINDOW).select_related("onboardingreminder")
    for user in users:
        reminder = getattr(user, "onboardingreminder", None)
        sent = reminder.sent_count if reminder else 0
        if sent >= len(ONBOARDING_REMINDERS_AFTER) or user.date_joined > now - ONBOARDING_REMINDERS_AFTER[sent]:
            continue
        if reminder and reminder.last_sent_at and reminder.last_sent_at > now - ONBOARDING_REMINDER_GAP:
            continue
        due.append(user)
    return due


def send_pending_reminder(pending, request=None):
    context = {"email": pending.email, "signup_url": signup_link(pending, request), "current_site": get_current_site(request)}
    get_adapter(request).send_mail("account/email/signup_reminder", pending.email, context)
    pending.reminder_sent_at = timezone.now()
    pending.save(update_fields=["reminder_sent_at"])


def send_onboarding_reminder(user, request=None):
    context = {
        "email": user.email,
        "login_url": absolute_url(reverse("account_login"), request),
        "reset_url": absolute_url(reverse("account_reset_password"), request),
        "current_site": get_current_site(request),
    }
    get_adapter(request).send_mail("account/email/onboarding_reminder", user.email, context)
    reminder, _ = OnboardingReminder.objects.get_or_create(user=user)
    reminder.sent_count += 1
    reminder.last_sent_at = timezone.now()
    reminder.save(update_fields=["sent_count", "last_sent_at"])
