from django import forms

from .models import Lead
from .services import EDITABLE_FIELDS, field_label

# Largest community partners CSV accepted
MAX_IMPORT_BYTES = 2 * 1024 * 1024


class RunForm(forms.Form):
    request = forms.CharField(widget=forms.Textarea(attrs={"rows": 2, "class": "staff-field w-full"}))


class LeadFilterForm(forms.Form):
    kind = forms.ChoiceField(choices=[("", "All kinds")] + Lead.Kind.choices, required=False)
    review_status = forms.ChoiceField(choices=[("", "Any review")] + Lead.ReviewStatus.choices, required=False)
    source = forms.ChoiceField(choices=[("", "Any source")] + Lead.Source.choices, required=False)
    q = forms.CharField(required=False)


class LeadForm(forms.ModelForm):
    """Edits a lead's fields for its kind; saving goes through services.update_lead."""

    class Meta:
        model = Lead
        fields = sorted({f for fields in EDITABLE_FIELDS.values() for f in fields})

    def __init__(self, lead, data=None):
        super().__init__(data, instance=Lead(**{f: getattr(lead, f) for f in self.Meta.fields}))
        for name in list(self.fields):
            if name not in EDITABLE_FIELDS[lead.kind]:
                del self.fields[name]
        self.order_fields(EDITABLE_FIELDS[lead.kind])
        for name, field in self.fields.items():
            field.label = field_label(name)
            field.widget.attrs["class"] = "staff-field w-full"
        if "justification" in self.fields:
            self.fields["justification"].widget.attrs["rows"] = 3


class PartnersImportForm(forms.Form):
    file = forms.FileField(
        label="Community partners CSV", help_text="Columns: EMAIL, and optionally Status (blank or Bounced #N)."
    )

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > MAX_IMPORT_BYTES:
            raise forms.ValidationError("The file is bigger than 2 MB.")
        return file
