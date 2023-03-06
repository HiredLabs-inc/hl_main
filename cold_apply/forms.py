from django import forms

from .models import Participant, Interaction


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ['name', 'email', 'phone', 'uploaded_resume']


class InteractionForm(forms.ModelForm):
    class Meta:
        model = Interaction
        fields = ['participant', 'interaction_type', 'notes']

