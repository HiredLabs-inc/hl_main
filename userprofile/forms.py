from django import forms
from django.contrib.auth.forms import (
    PasswordChangeForm,
    PasswordResetForm,
    UserCreationForm,
)
from django.contrib.auth.models import User
from django.utils.translation import gettext as _

from .models import Profile, VeteranProfile


class UserRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=101)
    last_name = forms.CharField(max_length=101)
    email = forms.EmailField()

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        ]


class ButtonRadioSelectWidget(forms.RadioSelect):
    template_name = "forms/widgets/button_radio_select.html"


class ProfileForm(forms.ModelForm):
    use_required_attribute = False

    def clean_is_veteran(self):
        is_veteran = self.cleaned_data["is_veteran"]
        if is_veteran is None:
            raise forms.ValidationError("This field is required.")
        return is_veteran

    class Meta:
        model = Profile
        fields = [
            "phone",
            "location",
            "linkedin",
            "is_veteran",
            "special_training",
            "special_skills",
            "job_links",
            "work_preferences",
        ]
        labels = {
            "is_veteran": _("Are you a US Military Veteran?"),
            "phone": "Contact Number (optional)",
            "linkedin": "LinkedIn (optional)",
        }
        widgets = {
            "special_training": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Please list any special training or certifications.",
                }
            ),
            "location": forms.TextInput(
                attrs={"placeholder": "Please enter your city and state."}
            ),
            "special_skills": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Please list any special skills or qualifications.",
                }
            ),
            "job_links": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Please list links to 2-3 job posts that interest you.",
                }
            ),
            "work_preferences": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Please list any preferences you have for your next job (e.g. location, industry, hours, "
                    "level, etc.).",
                }
            ),
            "is_veteran": ButtonRadioSelectWidget(
                choices=((True, "Yes"), (False, "No"))
            ),
        }


class VeteranProfileForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = VeteranProfile
        fields = [
            "service_branch",
            "military_specialiaty",
            "years_of_service",
            "rank_at_separation",
        ]


class UploadResumeForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["resume"]


class UserPasswordChangeForm(PasswordChangeForm):
    class Meta:
        model = User
        fields = ["password1", "password2"]


class UpdateProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["nickname"]


class UserPasswordResetForm(PasswordResetForm):
    class Meta:
        model = User
        fields = ["email"]


class ProfileServicePackageForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = Profile
        fields = ["service_package"]
        widgets = {"service_package": ButtonRadioSelectWidget}
