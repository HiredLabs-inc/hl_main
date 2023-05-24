from django import forms

from resume.models import Bullet

from .models import Participant, Interaction, Experience, Applicant, Skill


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
