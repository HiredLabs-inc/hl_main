from allauth.account.decorators import verified_email_required
from allauth.account.views import EmailView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from releases.models import App

from .forms import (
    PasswordResetForm,
    ProfileForm,
    ProfileServicePackageForm,
    UploadResumeForm,
    UserPasswordChangeForm,
    UserRegistrationForm,
    VeteranProfileForm,
)
from .models import OnboardingStep, Profile, VeteranProfile

ONBOARDING_STEP_NAMES = {value: label for value, label in OnboardingStep.choices}


@verified_email_required
def onboarding_home_view(request):
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user, defaults={})
    # profile.onboarding_step = OnboardingStep.PROFILE
    # profile.save()
    step = profile.onboarding_step

    if step == OnboardingStep.PROFILE:
        return redirect("userprofile:onboarding_profile")
    if step == OnboardingStep.VETERAN_PROFILE:
        return redirect("userprofile:onboarding_veteran_profile")
    if step == OnboardingStep.SERVICE_PACKAGE:
        return redirect("userprofile:onboarding_service_package")
    if step == OnboardingStep.UPLOAD_RESUME:
        return redirect("userprofile:onboarding_upload_resume")

    return redirect("cold_apply:index")


@verified_email_required
def onboarding_profile_view(request):
    profile: Profile = request.user.profile
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        if profile.onboarding_step == OnboardingStep.PROFILE:
            form.instance.increment_step()
        return redirect("userprofile:onboarding_home")

    step_name = ONBOARDING_STEP_NAMES[OnboardingStep.PROFILE]
    return render(
        request,
        "userprofile/onboarding_profile.html",
        {"form": form, "step_number": 1, "step_name": step_name},
    )


@verified_email_required
def onboarding_veteran_profile_view(request):
    profile: Profile = request.user.profile
    veteran_profile, _ = VeteranProfile.objects.get_or_create(user=request.user)
    form = VeteranProfileForm(request.POST or None, instance=veteran_profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        if profile.onboarding_step == OnboardingStep.VETERAN_PROFILE:
            profile.increment_step()
        return redirect("userprofile:onboarding_home")
    step_name = ONBOARDING_STEP_NAMES[OnboardingStep.VETERAN_PROFILE]
    return render(
        request,
        "userprofile/onboarding_veteran_profile.html",
        {
            "form": form,
            "step_number": 2,
            "step_name": step_name,
        },
    )


@verified_email_required
def onboarding_service_package_view(request):
    profile: Profile = request.user.profile
    form = ProfileServicePackageForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        if profile.onboarding_step == OnboardingStep.SERVICE_PACKAGE:
            profile.increment_step()
        return redirect("userprofile:onboarding_home")

    step_name = ONBOARDING_STEP_NAMES[OnboardingStep.SERVICE_PACKAGE]
    return render(
        request,
        "userprofile/onboarding_service_package.html",
        {"form": form, "step_number": 3, "step_name": step_name},
    )


@verified_email_required
def onboarding_upload_resume_view(request):
    profile: Profile = request.user.profile
    form = UploadResumeForm(request.POST or None, files=request.FILES, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        if profile.onboarding_step == OnboardingStep.UPLOAD_RESUME:
            profile.increment_step()
        return redirect("userprofile:onboarding_home")

    step_name = ONBOARDING_STEP_NAMES[OnboardingStep.UPLOAD_RESUME]
    return render(
        request,
        "userprofile/onboarding_upload_resume.html",
        {"form": form, "step_number": 4, "step_name": step_name},
    )


@login_required
def user_home(request):
    user = request.user

    if user.is_staff:
        return redirect("staff")

    if hasattr(user, "profile") and user.profile.is_onboard:
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
def profile_view(request):
    context = {"user_profile": request.user.profile}
    return render(request, "userprofile/profile_view.html", context)
