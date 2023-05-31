from django import forms

from resume.models import Bullet, Experience
from resume.pdf import (
    RESUME_TEMPLATE_SECTIONS,
    ResumeCoreTemplates,
    ResumeFormatChoices,
    ResumeSections,
)

from .models import Applicant, Interaction, Participant, Skill


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = [
            "name",
            "email",
            "phone",
            "veteran",
            "dnc",
            "uploaded_resume",
            "uploaded_resume_title",
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


class ApplicantForm(forms.ModelForm):
    class Meta:
        model = Applicant
        fields = [
            "name",
            "email",
            "phone",
            "linkedin",
            "location",
            "resume",
            "special_training",
            "special_skills",
            "job_links",
            "work_preferences",
            "service_branch",
            "military_specialiaty",
            "years_of_service",
            "rank_at_separation",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.NumberInput(attrs={"class": "form-control"}),
            "linkedin": forms.TextInput(attrs={"class": "form-control"}),
            "location": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Please enter your city and state.",
                }
            ),
            "resume": forms.FileInput(),
            "special_training": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Please list any special training or certifications.",
                }
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
            "service_branch": forms.Select(attrs={"class": "form-control"}),
            "military_specialiaty": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter N/A if not a veteran",
                }
            ),
            "years_of_service": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter 0 if not a veteran",
                }
            ),
            "rank_at_separation": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter N/A if not a veteran",
                }
            ),
        }


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ["title", "type"]


class BulletForm(forms.ModelForm):
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.order_by("title").all(),
        widget=forms.CheckboxSelectMultiple(),
        required=False,
    )

    class Meta:
        model = Bullet
        fields = ["text", "skills"]


class ResumeConfigForm(forms.Form):
    """
    Allows user to configure the tailored resume output
    """

    def __init__(self, *args, **kwargs) -> None:
        experiences = kwargs.pop("experiences")
        skills = kwargs.pop("skills")
        super().__init__(*args, **kwargs)
        self.fields["experiences"].queryset = experiences
        self.fields["experiences"].initial = experiences
        self.fields["skills"].queryset = skills
        self.fields["skills"].initial = skills

    # queryset for choices passed into constructor eg ResumeConfigForm(experiences=Experiences.objects.filter(...))
    experiences = forms.ModelMultipleChoiceField(
        queryset=Experience.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.none(),
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
    no_colors = forms.BooleanField(initial=False, widget=forms.CheckboxInput)

    resume_template_sections = {
        k: " | ".join(map(lambda s: s.capitalize(), v))
        for k, v in RESUME_TEMPLATE_SECTIONS.items()
    }
