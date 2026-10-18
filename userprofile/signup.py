"""Signup: email first, password after the emailed link is followed.

1. signup_view: email + bot check -> PendingSignup, email a signed link, show
   the "check your email" page. An email that already has an account gets a
   "log in or reset your password" email instead; the page looks the same.
2. signup_sent_view: that page, with Resend and "use a different email".
3. signup_complete_view: the link -> set a password -> create the verified
   User, log in, continue to onboarding.
"""
import logging
import smtplib

from allauth import ratelimit
from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.core import signing
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import SignupEmailForm
from .models import PendingSignup

logger = logging.getLogger(__name__)

LINK_MAX_AGE = 7 * 24 * 60 * 60
TOKEN_SALT = "userprofile.signup"
SESSION_EMAIL = "signup_email"
# Emails per address per hour (first send and resends together).
EMAILS_PER_HOUR = 5
SEND_ERROR = "We couldn't send the email just now. Please try again in a minute."


def make_token(email):
    return signing.dumps(email, salt=TOKEN_SALT)


def read_token(token):
    """(email, expired) for a validly signed token, or (None, False)."""
    try:
        return signing.loads(token, salt=TOKEN_SALT, max_age=LINK_MAX_AGE), False
    except signing.SignatureExpired:
        return signing.loads(token, salt=TOKEN_SALT), True
    except signing.BadSignature:
        return None, False


def absolute_url(path, request=None):
    """Full URL for links in emails; without a request (commands) uses PUBLIC_BASE_URL."""
    if request is not None:
        return request.build_absolute_uri(path)
    return settings.PUBLIC_BASE_URL + path


def signup_link(email, request=None):
    return absolute_url(reverse("signup_complete", args=[make_token(email)]), request)


def account_exists(email):
    return User.objects.filter(email__iexact=email).exists() or EmailAddress.objects.filter(email__iexact=email).exists()


def send_signup_email(request, email):
    """Email a signup link, or a login/reset reminder if the address already has
    an account. Returns an error message for the user, or None on success."""
    if not ratelimit.consume(request, action="signup_email", key=email, amount=EMAILS_PER_HOUR, duration=60 * 60):
        return "Too many emails were sent to this address. Please try again in an hour."

    context = {"email": email, "current_site": get_current_site(request)}
    pending = None
    if account_exists(email):
        template = "account/email/signup_existing"
        context["login_url"] = absolute_url(reverse("account_login"), request)
        context["reset_url"] = absolute_url(reverse("account_reset_password"), request)
    else:
        template = "account/email/signup_link"
        pending, _ = PendingSignup.objects.get_or_create(email=email)
        context["signup_url"] = signup_link(email, request)

    try:
        get_adapter(request).send_mail(template, email, context)
    except (smtplib.SMTPException, OSError) as e:
        logger.exception("Signup email to %s failed", email)
        if pending:
            pending.last_error = f"{timezone.now():%Y-%m-%d %H:%M} {e!r}"
            pending.save(update_fields=["last_error"])
        return SEND_ERROR

    if pending:
        pending.last_sent_at = timezone.now()
        pending.send_count += 1
        pending.last_error = ""
        pending.save(update_fields=["last_sent_at", "send_count", "last_error"])
    return None


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("userprofile:user_home")
    form = SignupEmailForm(request.POST or None, request=request, initial={"email": request.GET.get("email", "")})
    if request.method == "POST":
        too_many = ratelimit.consume_or_429(request, action="signup")
        if too_many:
            return too_many
        if form.is_valid():
            email = form.cleaned_data["email"]
            request.session[SESSION_EMAIL] = email
            error = send_signup_email(request, email)
            if error:
                return render(request, "account/signup_sent.html", {"email": email, "error": error})
            return redirect("signup_sent")
    return render(request, "account/signup.html", {"form": form})


def signup_sent_view(request):
    """'Check your email'. POST resends to the address saved in the session."""
    email = request.session.get(SESSION_EMAIL)
    if not email:
        return redirect("custom_account_signup")
    context = {"email": email}
    if request.method == "POST":
        context["error"] = send_signup_email(request, email)
        context["resent"] = not context["error"]
    return render(request, "account/signup_sent.html", context)


@require_POST
def signup_change_email_view(request):
    request.session.pop(SESSION_EMAIL, None)
    return redirect("custom_account_signup")


def signup_complete_view(request, token):
    email, expired = read_token(token)
    if email is None or expired:
        return render(request, "account/signup_link_invalid.html", {"email": email, "expired": expired})
    pending = PendingSignup.objects.filter(email=email, completed_at__isnull=True).first()
    if pending is None or account_exists(email):
        return render(request, "account/signup_link_invalid.html", {"email": email, "used": True})

    user = User(username=email, email=email)
    form = SetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Lock the row so a double submit can't create two users.
            pending = PendingSignup.objects.select_for_update().filter(pk=pending.pk, completed_at__isnull=True).first()
            if pending is None or account_exists(email):
                return render(request, "account/signup_link_invalid.html", {"email": email, "used": True})
            form.save()
            EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
            pending.completed_at = timezone.now()
            pending.save(update_fields=["completed_at"])
        request.session.pop(SESSION_EMAIL, None)
        login(request, user, backend="allauth.account.auth_backends.AuthenticationBackend")
        return redirect("userprofile:user_home")
    return render(request, "account/signup_set_password.html", {"form": form, "email": email})
