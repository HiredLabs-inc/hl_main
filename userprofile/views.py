from allauth.account.utils import send_email_confirmation
from allauth.account.views import EmailView
from allauth.decorators import rate_limit
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render
from django.urls import reverse

from cold_apply.guards import sign_up_completed
from releases.models import App
from userprofile.guards import verified_required
from userprofile.va_api import confirm_veteran_status

from .forms import (
    ProfileForm,
    ProfileServicePackageForm,
    UploadResumeForm,
    VeteranProfileForm,
)
from .models import OnboardingStep, Profile, VeteranProfile

ONBOARDING_STEP_NAMES = {value: label for value, label in OnboardingStep.choices}


def previous_step_response(request, profile):
    if "previous_step" in request.POST:
        profile.decrement_step()
        return redirect("userprofile:onboarding_home")
    return False


@login_required
@rate_limit(action="manage_email")
def verified_email_required_view(request):
    if "action_send" in request.POST:
        send_email_confirmation(request, request.user)

    request.user
    return render(request, "account/verified_email_required.html")


@verified_required
def onboarding_home_view(request):
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)
    step = profile.onboarding_step

    if step == OnboardingStep.PROFILE:
        return redirect("userprofile:onboarding_profile")
    if step == OnboardingStep.VETERAN_PROFILE:
        return redirect("userprofile:onboarding_veteran_profile")
    if step == OnboardingStep.SERVICE_PACKAGE:
        return redirect("userprofile:onboarding_service_package")
    if step == OnboardingStep.UPLOAD_RESUME:
        return redirect("userprofile:onboarding_upload_resume")

    # do redirect here when someone completes sign up

    return redirect("cold_apply:participant_detail", request.user.participant.id)


@verified_required
def onboarding_profile_view(request):
    profile: Profile = request.user.profile
    if previous_step := previous_step_response(request, profile):
        return previous_step
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        # form.instance.user = request.user
        form.save()
        form.instance.increment_step(OnboardingStep.PROFILE)
        return redirect("userprofile:onboarding_home")

    step_name = ONBOARDING_STEP_NAMES[OnboardingStep.PROFILE]
    return render(
        request,
        "userprofile/onboarding_profile.html",
        {"form": form, "step_number": 1, "step_name": step_name},
    )


@verified_required
def onboarding_veteran_profile_view(request):
    profile: Profile = request.user.profile
    if previous_step := previous_step_response(request, profile):
        return previous_step
    veteran_profile, _ = VeteranProfile.objects.get_or_create(user=request.user)

    form = VeteranProfileForm(request.POST or None, instance=veteran_profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        profile.increment_step(OnboardingStep.VETERAN_PROFILE)
        return redirect("userprofile:onboarding_home")
    step_name = ONBOARDING_STEP_NAMES[OnboardingStep.VETERAN_PROFILE]
    return render(
        request,
        "userprofile/onboarding_veteran_profile.html",
        {
            "form": form,
            "step_number": 2,
            "step_name": step_name,
            "profile": profile,
        },
    )


@verified_required
def onboarding_upload_resume_view(request):
    profile: Profile = request.user.profile
    if previous_step := previous_step_response(request, profile):
        return previous_step
    form = UploadResumeForm(
        request.POST or None, files=request.FILES or None, instance=profile
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        profile.increment_step(OnboardingStep.UPLOAD_RESUME)
        return redirect("userprofile:onboarding_home")

    step_name = ONBOARDING_STEP_NAMES[OnboardingStep.UPLOAD_RESUME]
    return render(
        request,
        "userprofile/onboarding_upload_resume.html",
        {"form": form, "step_number": 3, "step_name": step_name},
    )


@verified_required
def onboarding_service_package_view(request):
    profile: Profile = request.user.profile
    if previous_step := previous_step_response(request, profile):
        return previous_step
    form = ProfileServicePackageForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        profile.increment_step(OnboardingStep.SERVICE_PACKAGE)
        return redirect("userprofile:onboarding_home")

    step_name = ONBOARDING_STEP_NAMES[OnboardingStep.SERVICE_PACKAGE]
    return render(
        request,
        "userprofile/onboarding_service_package.html",
        {"form": form, "step_number": 4, "step_name": step_name},
    )


@login_required
def user_home(request):
    user = request.user

    if user.is_staff:
        return redirect("staff")

    if hasattr(user, "profile") and user.profile.is_onboarded:
        return redirect("cold_apply:home")

    return redirect("userprofile:onboarding_home")


def home(request):
    return render(request, "home.html")


def about(request):
    return render(request, "about.html")


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
