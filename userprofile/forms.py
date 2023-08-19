import logging
from typing import Any

from django import forms
from django.core.exceptions import BadRequest
from django.utils.translation import gettext as _

from userprofile.va_api import VAApiException, confirm_veteran_status

from .models import Profile, VeteranProfile

logger = logging.getLogger(__name__)


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

    def clean_is_veteran(self):
        is_veteran = self.cleaned_data["is_veteran"]
        if is_veteran is None:
            raise forms.ValidationError("This field is required.")
        return is_veteran

    field_order = [
        "first_name",
        "last_name",
        "city",
        "state",
        "zip_code",
        "phone",
        "linkedin",
        "special_training",
        "special_skills",
        "job_links",
        "work_preferences",
        "is_veteran",
    ]

    class Meta:
        model = Profile

        fields = [
            "is_veteran",
            "city",
            "state",
            "zip_code",
            "phone",
            "linkedin",
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

    def save(self, commit: bool = ...) -> Any:
        instance = super().save(commit)
        instance.user.first_name = self.cleaned_data["first_name"]
        instance.user.last_name = self.cleaned_data["last_name"]
        instance.user.save()
        return instance

    def clean(self):
        cleaned_data = super().clean()
        is_veteran = cleaned_data.get("is_veteran")
        if is_veteran:
            try:
                if confirm_veteran_status(self.instance.user):
                    self.instance.veteran_verified = True

            except (BadRequest, VAApiException) as bad_request:
                logger.error(
                    "is_veteran",
                    f"An error occurred while confirming your veteran status: {bad_request}",
                )
        return cleaned_data


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


class ProfileServicePackageForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = Profile
        fields = ["service_package"]
        widgets = {"service_package": ButtonRadioSelectWidget}
