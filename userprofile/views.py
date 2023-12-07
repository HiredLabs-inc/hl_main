import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from allauth.account.utils import send_email_confirmation
from allauth.account.views import SignupView
from django.conf import settings
from allauth.decorators import rate_limit
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render
from django.urls import reverse

# from cold_apply.guards import sign_up_completed
from releases.models import App
from userprofile.guards import verified_required
from userprofile.va_api import confirm_veteran_status

from .forms import (
    ProfileForm,
    ProfileServicePackageForm,
    UploadResumeForm,
    VeteranProfileForm,
    UploadServiceDocForm,
    VeteranStatusUpdateForm,
    CommentForm,
    CustomSignupForm,
)
from .models import OnboardingStep, Profile, VeteranProfile

from .static.scripts.storage.uploads import upload_file
from .static.scripts.storage.generate_signed_urls import generate_signed_url

# ONBOARDING_STEP_NAMES = {value: label for value, label in OnboardingStep.choices}


class CustomSignupView(SignupView):
    form_class = CustomSignupForm

# def previous_step_response(request, profile):
#     if "previous_step" in request.POST:
#         profile.decrement_step()
#         return redirect("userprofile:onboarding_home")
#     return False


@login_required
@rate_limit(action="manage_email")
def verified_email_required_view(request):
    if "action_send" in request.POST:
        # fromaddr = settings.EMAIL_HOST_USER
        # toaddr = request.user.email
        # msg = MIMEMultipart()
        # msg["From"] = fromaddr
        # msg["To"] = toaddr
        # msg["Subject"] = "Verify your email"
        # body = "Please verify your email by clicking the link below"
        # msg.attach(MIMEText(body, "plain"))
        # server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
        # server.ehlo()
        # server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        send_email_confirmation(request, request.user)
        # text = msg.as_string()
        # server.sendmail(fromaddr,toaddr,text)
        # server.quit()

    request.user
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

# @verified_required
# def onboarding_home_view(request):
#     user = request.user
#     profile, _ = Profile.objects.get_or_create(user=user)
#     step = profile.onboarding_step
#
#     if step == OnboardingStep.PROFILE:
#         return redirect("userprofile:onboarding_profile")
#     elif step == OnboardingStep.VETERAN_PROFILE:
#         return redirect("userprofile:onboarding_veteran_profile")
#     elif step == OnboardingStep.UPLOAD_SERVICE_DOC:
#         return redirect("userprofile:onboarding_upload_service_doc")
#     elif step == OnboardingStep.UPLOAD_RESUME:
#         return redirect("userprofile:onboarding_upload_resume")
#     elif step == OnboardingStep.SERVICE_PACKAGE:
#         return redirect("userprofile:onboarding_service_package")
#
#     # do redirect here when someone completes sign up
#
#     return redirect("cold_apply:participant_detail", request.user.participant.id)





# @verified_required
# def onboarding_profile_view(request):
#     profile: Profile = request.user.profile
#     if previous_step := previous_step_response(request, profile):
#         return previous_step
#     form = ProfileForm(request.POST or None, instance=profile)
#     if request.method == "POST" and form.is_valid():
#         form.save()
#         form.instance.increment_step(OnboardingStep.PROFILE)
#         return redirect("userprofile:onboarding_home")
#
#     step_name = ONBOARDING_STEP_NAMES[OnboardingStep.PROFILE]
#     return render(
#         request,
#         "userprofile/onboarding_profile.html",
#         {"form": form, "step_number": 1, "step_name": step_name},
#     )


# @verified_required
# def onboarding_veteran_profile_view(request):
#     profile: Profile = request.user.profile
#     if previous_step := previous_step_response(request, profile):
#         return previous_step
#     veteran_profile, _ = VeteranProfile.objects.get_or_create(user=request.user)
#
#     form = VeteranProfileForm(request.POST or None, instance=veteran_profile)
#     if request.method == "POST" and form.is_valid():
#         form.save()
#         profile.increment_step(OnboardingStep.VETERAN_PROFILE)
#         return redirect("userprofile:onboarding_home")
#     step_name = ONBOARDING_STEP_NAMES[OnboardingStep.VETERAN_PROFILE]
#     return render(
#         request,
#         "userprofile/onboarding_veteran_profile.html",
#         {
#             "form": form,
#             "step_number": 2,
#             "step_name": step_name,
#             "profile": profile,
#         },
#     )

# @verified_required
# def onboarding_upload_service_doc_view(request):
#     profile: Profile = request.user.profile
#     if previous_step := previous_step_response(request, profile):
#         return previous_step
#     veteran_profile = VeteranProfile.objects.get(user=request.user)
#     form = UploadServiceDocForm(
#         request.POST or None, files=request.FILES or None, instance=veteran_profile
#     )
#
#     if request.method == "POST" and form.is_valid():
#         form.save()
#         profile.increment_step(OnboardingStep.UPLOAD_SERVICE_DOC)
#         try:
#             upload_file(settings.GS_BUCKET_NAME, request.FILES["service_doc"].name, request.FILES["service_doc"].name)
#         except:
#             print("Error uploading file to GCS")
#         return redirect("userprofile:onboarding_home")
#
#     step_name = ONBOARDING_STEP_NAMES[OnboardingStep.UPLOAD_SERVICE_DOC]
#     return render(
#         request,
#         "userprofile/onboarding_upload_service_doc.html",
#         {"form": form, "step_number": 3, "step_name": step_name, "profile": profile, "veteran_profile": veteran_profile},
#     )

# @verified_required
# def onboarding_upload_resume_view(request):
#     profile: Profile = request.user.profile
#     if previous_step := previous_step_response(request, profile):
#         return previous_step
#     form = UploadResumeForm(
#         request.POST or None, files=request.FILES or None, instance=profile
#     )
#     if request.method == "POST" and form.is_valid():
#         form.save()
#         profile.increment_step(OnboardingStep.UPLOAD_RESUME)
#         return redirect("userprofile:onboarding_home")
#
#     step_name = ONBOARDING_STEP_NAMES[OnboardingStep.UPLOAD_RESUME]
#     return render(
#         request,
#         "userprofile/onboarding_upload_resume.html",
#         {"form": form, "step_number": 4, "step_name": step_name},
#     )


# @verified_required
# def onboarding_service_package_view(request):
#     profile: Profile = request.user.profile
#     if previous_step := previous_step_response(request, profile):
#         return previous_step
#     form = ProfileServicePackageForm(request.POST or None, instance=profile)
#     if request.method == "POST" and form.is_valid():
#         form.save()
#         profile.increment_step(OnboardingStep.SERVICE_PACKAGE)
#         return redirect("userprofile:onboarding_home")
#
#     step_name = ONBOARDING_STEP_NAMES[OnboardingStep.SERVICE_PACKAGE]
#     return render(
#         request,
#         "userprofile/onboarding_service_package.html",
#         {"form": form, "step_number": 5, "step_name": step_name},
#     )


@login_required
def user_home(request):
    user = request.user

    if user.is_staff:
        return redirect("staff")

    if hasattr(user, "profile") and user.profile.is_onboarded:
        return redirect("welcome")

    return redirect("userprofile:onboarding_view")

# Public views
def home(request):
    return render(request, "new_home.html")


def about(request):
    return render(request, "new_about.html")

def terms_of_service(request):
    return render(request, "TOS.html")

def privacy_policy(request):
    return render(request, "privacy_policy.html")

def how_it_works(request):
    return render(request, "how_it_works.html")

def contact(request):
    form = CommentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("thanks")
    return render(request, "secondary_actions.html", {"form": form})

def thanks(request):
    return render(request, "thanks.html")

def welcome(request):
    return render(request, "welcome.html")

# All views below require login
@login_required
def staff(request):
    context = {"apps": App.objects.all()}
    return render(request, "staff_home.html", context)


@login_required
# @sign_up_completed
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


@login_required
def update_veteran_status_view(request, participant_id):
    profile = Profile.objects.get(user=participant_id)
    veteran_profile = VeteranProfile.objects.get(user=participant_id)
    form = VeteranStatusUpdateForm(request.POST or None, instance=profile)
    signed_url = ''
    if not settings.DEBUG and veteran_profile.service_doc:
        signed_url = generate_signed_url(
            service_account_file=settings.SERVICE_ACCOUNT_FILE,
            bucket_name=settings.GS_BUCKET_NAME,
            object_name=veteran_profile.service_doc.name,
            subresource=None,
            expiration=604_800,
            http_method="GET",
            query_parameters=None,
            headers=None,
        )
    if request.method == "POST" and form.is_valid():
        form.save()
        # return redirect("cold_apply:participant_detail", participant_id=profile.user.id)
    context = {
        "form": form,
        "profile": profile,
        "veteran_profile": veteran_profile,
        "signed_url": signed_url,
        "debug": settings.DEBUG,
    }
    return render(request, "userprofile/veteran_status_update_view.html", context)
