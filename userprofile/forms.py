import logging
from typing import Any

from django import forms
from django.core.exceptions import BadRequest
from django.utils.translation import gettext as _
from django.conf import settings

from allauth.account.adapter import get_adapter
from allauth.account.forms import ResetPasswordForm
from userprofile.va_api import VAApiException, confirm_veteran_status
from . import turnstile
from .models import Profile, VeteranProfile, Comment

logger = logging.getLogger(__name__)

class HoneypotInput(forms.TextInput):
    """A text input that people never see (components/form_input.html hides
    fields whose widget is_hidden) but form-filling bots do."""

    is_hidden = True

    def __init__(self):
        super().__init__(attrs={"autocomplete": "off", "tabindex": "-1"})


class BotCheckForm(forms.Form):
    """Honeypot plus Cloudflare Turnstile. Templates include
    components/bot_check.html to render the widget. Pass request= so Cloudflare
    also gets the client IP (optional)."""

    BOT_CHECK_ERROR = _("We couldn't confirm you're a person. Please try again.")

    website = forms.CharField(required=False, label="Leave this empty", widget=HoneypotInput())

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

    @property
    def turnstile_site_key(self):
        return settings.TURNSTILE_SITE_KEY

    def clean(self):
        cleaned_data = super().clean()
        remote_ip = get_adapter().get_client_ip(self.request) if self.request else None
        if self.cleaned_data.get("website") or not turnstile.verify(
            self.data.get(turnstile.RESPONSE_FIELD), remote_ip
        ):
            raise forms.ValidationError(self.BOT_CHECK_ERROR)
        return cleaned_data


class SignupEmailForm(BotCheckForm):
    # User.username holds the email and is limited to 150 characters.
    email = forms.EmailField(
        max_length=150,
        label=_("Email"),
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": _("you@example.com")}),
    )

    field_order = ["email", "website"]

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class BotCheckedResetPasswordForm(BotCheckForm, ResetPasswordForm):
    field_order = ["email", "website"]


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
        CHOICES = {"True": "Yes", "False": "No"}
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
            "bootcamp",
        ]

        labels = {
            "phone": "Phone Number",
            "linkedin": "LinkedIn",
            "service_doc": "DD214 or other service documentation REDACT SSN BEFORE UPLOADING",
            "bootcamp": "Are you interested in a free coding bootcamp?",
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
            "bootcamp": forms.RadioSelect(choices=CHOICES.items()),
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

class CommentForm(BotCheckForm, forms.ModelForm):
    name = forms.CharField(max_length=200)
    email = forms.EmailField()
    comment = forms.CharField(widget=forms.Textarea)

    field_order = ["name", "email", "comment", "website"]

    class Meta:
        model = Comment
        fields = ["name", "email", "comment"]
