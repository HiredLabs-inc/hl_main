from django import forms

from .models import Participant, Interaction, Experience


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ['name', 'email', 'phone', 'veteran', 'dnc',
                  'uploaded_resume', 'uploaded_resume_title', 'current_step']


class InteractionForm(forms.ModelForm):
    class Meta:
        model = Interaction
        fields = ['participant', 'interaction_type', 'notes']


class ExperienceForm(forms.ModelForm):
    class Meta:
        model = Experience
        start_date = forms.DateField(
            input_formats=['%m/%d/%Y'],
            widget=forms.DateInput(attrs={
                'class': 'form-control datetimepicker-input',
                'data-target': '#datetimepicker1'
            }
            ))
        fields = ['position', 'org', 'start_date', 'end_date']
