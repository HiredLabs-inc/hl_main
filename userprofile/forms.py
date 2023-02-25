from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm, PasswordResetForm
from django.contrib.auth.models import User

from .models import Profile


class UserRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=101)
    last_name = forms.CharField(max_length=101)
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', \
                  'email', 'password1', 'password2']


class CompleteProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['nickname']


class UserPasswordChangeForm(PasswordChangeForm):
    class Meta:
        model = User
        fields = ['password1', 'password2']


class UpdateProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['nickname']


class UserPasswordResetForm(PasswordResetForm):
    class Meta:
        model = User
        fields = ['email']