"""Staff page listing people stuck in signup, with resend/remind/delete actions."""
import smtplib

from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import reminders
from .guards import staff_required
from .models import PendingSignup
from .signup import send_signup_email

# The unfinished-users list can include many legacy accounts; show the newest.
MAX_ROWS = 200


@staff_required
def stuck_signups_view(request):
    context = {
        "pending": PendingSignup.objects.filter(completed_at__isnull=True).order_by("-created_at")[:MAX_ROWS],
        "users": reminders.unfinished_users().select_related("onboardingreminder").order_by("-date_joined")[:MAX_ROWS],
        "max_rows": MAX_ROWS,
    }
    return render(request, "userprofile/stuck_signups.html", context)


@staff_required
@require_POST
def stuck_signup_action_view(request, kind, pk, action):
    if kind == "pending":
        pending = get_object_or_404(PendingSignup, pk=pk, completed_at__isnull=True)
        email = pending.email
        if action == "resend":
            error = send_signup_email(request, email)
            messages.add_message(request, messages.ERROR if error else messages.SUCCESS, error or f"Sent a new signup link to {email}.")
        elif action == "delete":
            pending.delete()
            messages.success(request, f"Deleted the pending signup for {email}.")
    elif kind == "user":
        user = get_object_or_404(reminders.unfinished_users(), pk=pk)
        email = user.email
        if action == "remind":
            try:
                reminders.send_onboarding_reminder(user, request)
                messages.success(request, f"Sent an onboarding reminder to {email}.")
            except (smtplib.SMTPException, OSError) as e:
                messages.error(request, f"Couldn't send to {email}: {e}")
        elif action == "delete":
            user.delete()
            messages.success(request, f"Deleted the account for {email}.")
    return redirect("stuck_signups")
