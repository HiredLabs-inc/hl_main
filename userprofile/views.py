from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse

from releases.models import App
from .forms import UserRegistrationForm, CompleteProfileForm, UserPasswordChangeForm, PasswordResetForm
# Import any models needed for views. Note: all views accessing db should require login
from .models import Profile


# Import other python packages, includes ones you wrote. "script_name" is the name of the .py file
# containing ClassName, which is the desired import

# from .top_level.package_directory.script_name import ClassName

# These pages are accessible without a login.

# MOVE TO userprofile app
def home(request):
    return render(request, 'home.html')


def about(request):
    return render(request, 'about.html')


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()

            messages.success(request, 'Your account has been created.\n\
            You can now log in.')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    context = {'form': form}
    return render(request, 'userprofile/register.html', context)


# All views below require login
@login_required
def staff(request):
    context = {'apps': App.objects.all()}
    return render(request, 'staff_home.html', context)


@login_required
def profile_view(request):
    user_profile = Profile.objects.all() \
        .filter(user=request.user) \
        .values()
    context = {'user_profile': user_profile}
    return render(request, 'userprofile/profile_view.html', context)


@login_required
def complete_profile(request):
    if request.method == 'POST':
        form = CompleteProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            return redirect(reverse('userprofile:profile_view'))
    else:
        form = CompleteProfileForm()
    context = {'form': form}
    return render(request, 'userprofile/complete_profile.html', context)


@login_required
def password_change(request):
    if request.method == 'POST':
        form = UserPasswordChangeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse('userprofile:password_change_done'))
    else:
        form = UserPasswordChangeForm()
    context = {'form': form}
    return render(request, 'userprofile/password_change.html', context)


@login_required
def update_profile(request):
    if request.method == 'POST':
        form = CompleteProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            return redirect(reverse('userprofile:profile_view'))
    else:
        form = CompleteProfileForm(initial={
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'nickname': request.user.profile.nickname,
        })
    context = {
        'form': form,
    }
    return render(request, 'userprofile/update_profile.html', context)


@login_required
def password_reset(request):
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            form.subject_template_name = 'userprofile/password_reset_subject.txt'
            form.email_template_name = 'userprofile/password_reset_email.html'
            form.save()
            return redirect(reverse('userprofile:password_reset_done'))
    return render(request, 'userprofile/password_reset.html')
