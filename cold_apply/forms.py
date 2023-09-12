from typing import Any, Dict

from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator

from cold_apply.models import DatePostedFilter
from cold_apply.text_generation import (
    generate_bullet,
    generate_bullets,
    generate_overview,
)
from resume.models import Bullet, CertProjectActivity, Experience, Overview, Position
from resume.pdf import (
    RESUME_TEMPLATE_SECTIONS,
    ResumeCoreTemplates,
    ResumeFormatChoices,
    ResumeSections,
)

from .models import Interaction, Job, Participant, Skill


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = [
            "current_step",
        ]


class InteractionForm(forms.ModelForm):
    class Meta:
        model = Interaction
        fields = ["participant", "interaction_type", "notes"]


class ExperienceForm(forms.ModelForm):
    class Meta:
        model = Experience
        start_date = forms.DateField(
            input_formats=["%m/%d/%Y"],
            widget=forms.DateInput(
                attrs={
                    "class": "form-control datetimepicker-input",
                    "data-target": "#datetimepicker1",
                }
            ),
        )
        fields = ["position", "org", "start_date", "end_date"]


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ["title", "type"]


class OverviewForm(forms.ModelForm):
    position: Position
    job: Job

    def __init__(self, position, job, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.fields["auto_generate"]:
            self.fields["text"].required = False
        self.position = position
        self.job = job

    auto_generate = forms.BooleanField(
        widget=forms.RadioSelect(
            choices=(
                (False, "Manual"),
                (True, "Auto Generate"),
            ),
        ),
        initial=False,
        required=False,
    )

    def save(self, commit: bool = ...) -> Any:
        self.instance.title = self.position

        if self.cleaned_data["auto_generate"]:
            self.instance.auto_generated = True
            overview_text = generate_overview(self.instance.title, self.job)
            self.instance.text = overview_text
        else:
            self.instance.auto_generated = False
        return super().save(commit)

    class Meta:
        model = Overview
        fields = ["text"]


class BulletUpdateForm(forms.ModelForm):
    experience = forms.ModelChoiceField(
        queryset=Experience.objects.none(), empty_label=None
    )

    def __init__(self, participant, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["experience"].queryset = Experience.objects.filter(
            participant=participant
        )

    class Meta:
        model = Bullet
        fields = ["text", "skills", "experience"]
        widgets = {
            "skills": forms.CheckboxSelectMultiple(),
            "text": forms.Textarea(attrs={"rows": 4}),
        }

    def save(self, commit=True) -> Any:
        self.instance.auto_generated = False
        return super().save(commit)


class BulletCreateForm(forms.ModelForm):
    use_required_attribute = False
    auto_generate = forms.BooleanField(
        widget=forms.RadioSelect(
            choices=(
                (False, "Manual"),
                (True, "Auto Generate"),
            ),
        ),
        initial=False,
        required=False,
    )
    quantity = forms.IntegerField(required=False, min_value=1, initial=1)
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.order_by("title").all(),
        widget=forms.CheckboxSelectMultiple(),
        required=False,
    )
    experience = forms.ModelChoiceField(
        queryset=Experience.objects.none(), empty_label=None
    )
    remaning_bullet_count = 0

    def __init__(self, participant, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.fields["experience"].queryset = Experience.objects.filter(
            participant=participant
        )

        bullet_count = Bullet.objects.filter(
            experience__participant=participant
        ).count()

        self.remaning_bullet_count = Bullet.MAX_PER_PARTICIPANT - (bullet_count or 0)
        if self.remaning_bullet_count < 0:
            self.remaning_bullet_count = 0

        if kwargs.get("data", {}).get("auto_generate") == "True":
            self.fields["text"].required = False
            self.fields["quantity"].required = True

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if self.fields["quantity"].required:
            if quantity > self.remaning_bullet_count:
                raise forms.ValidationError(
                    f"Only {self.remaning_bullet_count} bullets remaining of {Bullet.MAX_PER_PARTICIPANT} limit."
                )
        return quantity

    def clean(self) -> Dict[str, Any]:
        if (
            self.cleaned_data["experience"] is None
            and self.cleaned_data["skills"] is None
        ):
            raise forms.ValidationError("Experience or Skills are required")

        if self.remaning_bullet_count == 0:
            raise forms.ValidationError(
                f"Bullet limit of {Bullet.MAX_PER_PARTICIPANT} reached."
            )
        return super().clean()

    def save(self, commit=True):
        if self.cleaned_data["auto_generate"]:
            bullets = generate_bullets(
                self.cleaned_data["experience"],
                self.cleaned_data["skills"],
                self.cleaned_data["quantity"],
            )
            for bullet_text in bullets:
                self.instance.id = None
                self.instance.auto_generated = True
                bullet_text = bullet_text
                self.instance.text = bullet_text
                super().save(commit)
            return self.instance

        return super().save(commit)

    class Meta:
        model = Bullet
        fields = ["text", "skills", "experience"]


class ResumeConfigForm(forms.Form):
    """
    Allows user to configure the tailored resume output
    """

    def __init__(self, *args, **kwargs) -> None:
        experiences = kwargs.pop("experiences")
        skills = kwargs.pop("skills")
        certifications = kwargs.pop("certifications")
        super().__init__(*args, **kwargs)
        self.fields["experiences"].queryset = experiences
        self.fields["skills"].queryset = skills
        self.fields["extra_skills"].queryset = skills
        self.fields["certifications"].queryset = certifications

    # queryset for choices passed into constructor eg ResumeConfigForm(experiences=Experiences.objects.filter(...))
    experiences = forms.ModelMultipleChoiceField(
        queryset=Experience.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    # for main bullet section
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    # for extra skills section
    extra_skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    certifications = forms.ModelMultipleChoiceField(
        queryset=CertProjectActivity.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    sections = forms.MultipleChoiceField(
        choices=ResumeSections.choices,
        initial=[
            ResumeSections.OVERVIEW,
            ResumeSections.EDUCATION,
        ],
        widget=forms.CheckboxSelectMultiple,
    )
    bullets_content = forms.ChoiceField(
        choices=ResumeFormatChoices.choices,
        widget=forms.RadioSelect,
        initial=ResumeFormatChoices.CHRONOLOGICAL,
    )
    resume_template = forms.ChoiceField(
        choices=ResumeCoreTemplates.choices,
        initial=ResumeCoreTemplates.STANDARD,
        widget=forms.RadioSelect,
    )
    preview = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.HiddenInput,
    )
    no_colors = forms.BooleanField(
        label="No colors", initial=False, widget=forms.CheckboxInput(), required=False
    )

    resume_template_sections = {
        k: " | ".join(map(lambda s: s.capitalize(), v))
        for k, v in RESUME_TEMPLATE_SECTIONS.items()
    }


class NewJobSelectionForm(forms.Form):
    def __init__(self, *args, **kwargs) -> None:
        participant = kwargs.pop("participant")
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["keep"].queryset = Job.objects.filter(
            participant=participant, status="New"
        )
        self.fields["discard"].queryset = Job.objects.filter(
            participant=participant, status="New"
        )
        self.user = user

    keep = forms.ModelMultipleChoiceField(queryset=Job.objects.none(), required=False)
    discard = forms.ModelMultipleChoiceField(
        queryset=Job.objects.none(), required=False
    )

    def save(self):
        self.cleaned_data["keep"].update(status="Open")
        reason = (
            "Admin Rejected"
            if (self.user.is_staff or self.user.is_superuser)
            else "Candidate Rejected by User"
        )
        self.cleaned_data["discard"].update(status="Closed", status_reason=reason)


class FindNewJobsForm(forms.Form):
    query = forms.CharField(max_length=100)
    keywords = forms.CharField(max_length=100, required=False)
    date_posted = forms.ChoiceField(
        required=True,
        choices=DatePostedFilter.choices,
        initial=DatePostedFilter.THREE_DAYS,
    )
