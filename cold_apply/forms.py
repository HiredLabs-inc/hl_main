from django import forms

from .models import Participant, Interaction


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ['name', 'email', 'phone', 'veteran', 'dnc',
                  'uploaded_resume', 'uploaded_resume_title', 'current_step']


class InteractionForm(forms.ModelForm):
    class Meta:
        model = Interaction
        fields = ['participant', 'interaction_type', 'notes']

