from django import forms

from .models import RateRequest


class RateRequestForm(forms.ModelForm):

    class Meta:
        model = RateRequest
        fields = ['skill', 'level', 'employer_country', 'worker_country', 'rate']
