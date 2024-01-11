import logging
from typing import Any

from django import forms
from django.core.exceptions import BadRequest
from django.utils.translation import gettext as _
from django.contrib.auth.models import User

from userprofile.va_api import VAApiException, confirm_veteran_status
from allauth.account.forms import SignupForm
from .models import Profile, VeteranProfile, Comment

logger = logging.getLogger(__name__)

class CustomSignupForm(SignupForm):
    class Meta:
        model = User
        fields = ["email"]

    def __init__(self, *args, **kwargs):
        super(CustomSignupForm, self).__init__(*args, **kwargs)
        self.fields.pop('password1')
        self.fields.pop('password2')

    def save(self, request):
        user = super(CustomSignupForm, self).save(request)
        user.set_unusable_password()
        user.save()
        return user

class ButtonRadioSelectWidget(forms.RadioSelect):
    template_name = "forms/widgets/button_radio_select.html"

class ProfileForm(forms.ModelForm):
    use_required_attribute = False

    first_name = forms.CharField(max_length=101)
    last_name = forms.CharField(max_length=101)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].initial = self.instance.user.first_name
        self.fields["last_name"].initial = self.instance.user.last_name

    field_order = [
        "first_name",
        "last_name",
        "city",
        "state",
        "phone",
        "linkedin",
        "special_training",
        "special_skills",
        "job_links",
        "work_preferences",
        "service_branch",
        "military_specialiaty",
        "years_of_service",
        "rank_at_separation",
        "resume",
        "service_doc",
    ]

    class Meta:
        model = Profile

        fields = [
            "first_name",
            "last_name",
            "city",
            "state",
            "phone",
            "linkedin",
            "special_training",
            "special_skills",
            "job_links",
            "work_preferences",
            "service_branch",
            "military_specialiaty",
            "years_of_service",
            "rank_at_separation",
            "resume",
            "service_doc",
        ]

        labels = {
            "phone": "Phone Number",
            "linkedin": "LinkedIn",
            "service_doc": "DD214 or other service documentation",
        }
        widgets = {
            "special_training": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Please list any special training or certifications that you have or are working towards.",
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
                    "placeholder": "Please list any preferences you have for your next job (e.g. location, industry, hours, level, etc.).",
                }
            ),
        }

    def save(self, commit: bool = ...) -> Any:
        instance = super().save(commit)
        instance.user.first_name = self.cleaned_data["first_name"]
        instance.user.last_name = self.cleaned_data["last_name"]
        instance.user.save()
        return instance

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

class UploadServiceDocForm(forms.ModelForm):
    class Meta:
        model = VeteranProfile
        fields = ["service_doc"]

class ProfileServicePackageForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = Profile
        fields = ["service_package"]
        widgets = {"service_package": ButtonRadioSelectWidget}

class VeteranStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["veteran_verified", "is_veteran"]

class CommentForm(forms.ModelForm):
    name = forms.CharField(max_length=200)
    email = forms.EmailField()
    comment = forms.CharField(widget=forms.Textarea)
    class Meta:
        model = Comment
        fields = ["name", "email", "comment"]
