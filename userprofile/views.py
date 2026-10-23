import logging
import smtplib

from allauth.account.utils import send_email_confirmation
from django.conf import settings
from allauth.decorators import rate_limit
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMessage
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from userprofile.guards import is_volunteer, verified_required, veteran_reviewer_required
from userprofile.intake import awaiting_veteran_review, verify_and_advance
from userprofile.va_api import confirm_veteran_status

from .forms import (
    ProfileForm,
    ProfileServicePackageForm,
    UploadResumeForm,
    VeteranProfileForm,
    UploadServiceDocForm,
    VeteranStatusUpdateForm,
    CommentForm,
)
from . import testimonials
from .models import BootCampSession, OnboardingStep, Profile, VeteranProfile

from hl_main.gcs import SIGNED_URL_EXPIRATION, generate_signed_url
from pipeline import services

logger = logging.getLogger(__name__)
# Who opened which service document; kept at INFO in production (settings/cloud.py)
audit_logger = logging.getLogger("hl_main.audit")

@login_required
@rate_limit(action="manage_email")
def verified_email_required_view(request):
    if "action_send" in request.POST:
        send_email_confirmation(request, request.user)

    return render(request, "account/verified_email_required.html")

@verified_required
def onboarding_view(request):
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        profile.handle_onboard_complete()
        return redirect("welcome")
    return render(request, "userprofile/onboarding.html", {"form": form})

@login_required
def user_home(request):
    user = request.user

    if user.is_staff:
        return redirect("staff")

    if is_volunteer(user):
        return redirect("volunteer_home")

    if hasattr(user, "profile") and user.profile.is_onboarded:
        return redirect("welcome")

    return redirect("userprofile:onboarding_view")

# Public views
def home(request):
    return render(
        request,
        "new_home.html",
        {"next_bootcamp": BootCampSession.next_session(), "testimonials": testimonials.HOMEPAGE},
    )

def about(request):
    return render(request, "new_about.html")

def terms_of_service(request):
    return render(request, "TOS.html")

def privacy_policy(request):
    return render(request, "privacy_policy.html")

def how_it_works(request):
    return render(
        request,
        "how_it_works.html",
        {"next_bootcamp": BootCampSession.next_session(), "testimonial": testimonials.SERVICES_FEATURE},
    )

def impact(request):
    return render(request, 'impact.html')

def contact(request):
    form = CommentForm(request.POST or None, request=request)
    if request.method == "POST" and form.is_valid():
        notify_comment(request, form.save())
        return redirect("thanks")
    return render(request, "secondary_actions.html", {"form": form})

def notify_comment(request, comment):
    """Email a new contact-form comment to the team. Replying answers the commenter.
    A failed send is logged; the comment is already saved and visible in admin."""
    admin_url = request.build_absolute_uri(reverse("admin:userprofile_comment_change", args=[comment.pk]))
    message = EmailMessage(
        # A newline in a header is rejected, so flatten the name
        subject=f"New comment from {' '.join(comment.name.split())}",
        body=f"{comment.name} <{comment.email}> wrote:\n\n{comment.comment}\n\nIn admin: {admin_url}\n",
        to=settings.COMMENT_NOTIFICATION_EMAILS,
        reply_to=[comment.email],
    )
    try:
        message.send()
    except (smtplib.SMTPException, OSError):
        logger.exception("Comment notification for comment %s failed", comment.pk)

def thanks(request):
    return render(request, "thanks.html")

def welcome(request):
    return render(request, "welcome.html")

# All views below require login
@login_required
def profile_view(request):
    user_profile = Profile.objects.get_or_create(user=request.user)
    context = {"user_profile": user_profile}
    return render(request, "userprofile/profile_view.html", context)

@login_required
def profile_update_view(request):
    form = ProfileForm(request.POST or None, instance=request.user.profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("userprofile:profile_view")
    return render(request, "userprofile/profile_update_view.html", {"form": form})

@veteran_reviewer_required
def update_veteran_status_view(request, participant_id):
    profile = get_object_or_404(Profile, user=participant_id)
    if request.method == "POST" and "verify_and_advance" in request.POST:
        enrollment = verify_and_advance(profile, request.user)
        if enrollment is None:
            messages.error(request, "They aren't waiting for veteran review, so nothing was moved.")
        else:
            messages.success(request, f"Verified and moved to {enrollment.current_step.title}.")
        return redirect("userprofile:veteran_status_update_view", participant_id=profile.user_id)
    form = VeteranStatusUpdateForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
    context = {
        "form": form,
        "profile": profile,
        "awaiting_review": awaiting_veteran_review(profile.user),
    }
    return render(request, "userprofile/veteran_status_update_view.html", context)


@veteran_reviewer_required
def service_doc_view(request, user_pk):
    """The only way to open a service document (DD214): logs who opened it (audit log
    and the person's timeline), then redirects to a short-lived signed URL, or
    streams the local file in development"""
    profile = get_object_or_404(Profile, user=user_pk)
    if not profile.service_doc:
        raise Http404
    audit_logger.info("Service document of user %s opened by user %s", profile.user_id, request.user.pk)
    services.record_document_opened(profile.user, request.user, "DD214")
    if settings.DEBUG:
        return FileResponse(profile.service_doc.open("rb"))
    return redirect(
        generate_signed_url(
            bucket_name=settings.GS_BUCKET_NAME,
            object_name=profile.service_doc.name,
            expiration=SIGNED_URL_EXPIRATION,
        )
    )
