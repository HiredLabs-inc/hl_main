from django import forms
from django.conf import settings

from .agents import get_agent_type
from .models import AgentConfig, AgentLimits, Lead, ProviderConfig, TaskConfig
from .services import EDITABLE_FIELDS, field_label, stage_choices
from .tools import TOOLS

# Largest community partners CSV accepted
MAX_IMPORT_BYTES = 2 * 1024 * 1024


class RunForm(forms.Form):
    request = forms.CharField(widget=forms.Textarea(attrs={"rows": 2, "class": "staff-field w-full"}))


class FollowUpForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 2, "class": "staff-field w-full"}))


def _style(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            widget.attrs.setdefault("class", "rounded border-hl-line text-hl-blue focus:ring-hl-blue")
        else:
            widget.attrs.setdefault("class", "staff-field w-full")


def _description_field(name):
    return f"description_{name}"


class AgentConfigForm(forms.ModelForm):
    """An agent's settings. The type is fixed once the agent exists, because its
    runs and leads depend on it."""

    tools = forms.MultipleChoiceField(
        choices=[(name, name) for name in TOOLS], required=False, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = AgentConfig
        fields = ["name", "agent_type", "provider", "model", "default_request", "system_prompt", "tools", "max_iterations", "active"]
        labels = {"agent_type": "Type", "default_request": "Default request", "max_iterations": "Most steps per run"}
        help_texts = {
            "model": "As the provider names it, e.g. gemma4:31b. Takes effect on the next run.",
            "system_prompt": "Tells the agent what to find and to reply with only a JSON list of the type's fields.",
            "max_iterations": "Model calls per run or follow-up before it stops without an answer.",
            "active": "Inactive agents aren't shown on the Agents page.",
        }
        widgets = {
            "default_request": forms.Textarea(attrs={"rows": 2}),
            "system_prompt": forms.Textarea(attrs={"rows": 20, "class": "staff-field w-full font-mono text-xs"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        providers = ProviderConfig.objects.filter(active=True)
        if self.instance.provider_id:
            providers = providers | ProviderConfig.objects.filter(pk=self.instance.provider_id)
        self.fields["provider"].queryset = providers.distinct()
        if self.instance.pk:
            self.fields["agent_type"].disabled = True
            self.fields["agent_type"].help_text = "Fixed once the agent exists. Copy it to make one of another type."
            self.fields["agent_type"].widget.attrs["class"] = "staff-field w-full bg-hl-mist text-hl-muted"
        for name, tool in TOOLS.items():
            self.fields[_description_field(name)] = forms.CharField(
                label=f"{name} description",
                required=False,
                initial=self.instance.tool_descriptions.get(name, ""),
                help_text=f"Leave blank for the default: {tool.description}",
                widget=forms.Textarea(attrs={"rows": 2}),
            )
        fields = self.Meta.fields
        tools_at = fields.index("tools") + 1
        self.order_fields(fields[:tools_at] + [_description_field(name) for name in TOOLS] + fields[tools_at:])
        _style(self)

    def clean(self):
        cleaned = super().clean()
        agent_type = cleaned.get("agent_type")
        if agent_type:
            allowed = get_agent_type(agent_type).allowed_tools
            if not_allowed := [name for name in cleaned.get("tools", []) if name not in allowed]:
                self.add_error("tools", f"This type can't use {', '.join(not_allowed)}.")
        provider = cleaned.get("provider")
        if provider and provider.kind == ProviderConfig.Kind.GEMINI:
            self.add_error("provider", "Gemini can't run agents yet, because agents need tools (IDEA-008).")
        return cleaned

    def save(self, commit=True):
        self.instance.tool_descriptions = {
            name: text
            for name in TOOLS
            if (text := self.cleaned_data[_description_field(name)].strip())
        }
        return super().save(commit)


class ProviderConfigForm(forms.ModelForm):
    secret_env = forms.ChoiceField(
        label="API key",
        required=False,
        help_text="The env var (a Secret Manager secret on Cloud Run) that holds the key. Add names in "
        "HLAGENTS_PROVIDER_SECRETS. Keys are never stored here.",
    )
    input_cost_per_mtok = forms.DecimalField(label="Input $ per million tokens", min_value=0, decimal_places=4)
    output_cost_per_mtok = forms.DecimalField(label="Output $ per million tokens", min_value=0, decimal_places=4)

    class Meta:
        model = ProviderConfig
        fields = ["name", "kind", "base_url", "location", "secret_env", "input_cost_per_mtok", "output_cost_per_mtok", "active"]
        labels = {"base_url": "Base URL"}
        help_texts = {
            "base_url": "Ollama only. Leave blank for Ollama Cloud. The API key is sent here.",
            "location": f"Gemini only: the Vertex AI location. Leave blank for {settings.GEMINI_LOCATION}. "
            "Gemini uses the server's Google credentials, so it needs no API key.",
            "active": "Agents can't start runs on an inactive provider.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["secret_env"].choices = [("", "No key")] + [(name, name) for name in settings.HLAGENTS_PROVIDER_SECRETS]
        self.fields["input_cost_per_mtok"].help_text = "Estimates for the cost cap. 0 for a subscription."
        _style(self)


class TaskConfigForm(forms.ModelForm):
    """A task's settings. The key is fixed: the app that runs the task looks it up."""

    class Meta:
        model = TaskConfig
        fields = ["provider", "model", "instructions", "options", "active"]
        help_texts = {
            "model": "As the provider names it, e.g. gemini-3.8-flash or gemma4:31b. Takes effect on the next call.",
            "instructions": "The system prompt. The app adds what to write about (a job title, skills, keywords).",
            "options": 'JSON. Any of temperature, top_p, top_k, max_output_tokens and thinking_budget (Gemini), '
            'e.g. {"temperature": 0.5, "max_output_tokens": 1024}.',
            "active": "An inactive task fails every call with a message, instead of calling the provider.",
        }
        widgets = {
            "instructions": forms.Textarea(attrs={"rows": 16, "class": "staff-field w-full font-mono text-xs"}),
            "options": forms.Textarea(attrs={"rows": 3, "class": "staff-field w-full font-mono text-xs"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        providers = ProviderConfig.objects.filter(active=True)
        if self.instance.provider_id:
            providers = providers | ProviderConfig.objects.filter(pk=self.instance.provider_id)
        self.fields["provider"].queryset = providers.distinct()
        _style(self)

    def clean_options(self):
        options = self.cleaned_data["options"]
        if not isinstance(options, dict):
            raise forms.ValidationError('Options must be a JSON object, e.g. {"temperature": 0.5}.')
        return options


def _tool_cost_field(name):
    return f"tool_cost_{name}"


class LimitsForm(forms.ModelForm):
    run_cost_cap = forms.DecimalField(label="Run cap ($)", min_value=0, decimal_places=2)
    daily_cost_cap = forms.DecimalField(label="Daily cap ($)", min_value=0, decimal_places=2)

    class Meta:
        model = AgentLimits
        fields = ["run_cost_cap", "daily_cost_cap"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["run_cost_cap"].help_text = "A run, with its follow-ups, stops when its estimated cost gets here."
        self.fields["daily_cost_cap"].help_text = (
            "No run starts or continues, and no task runs, once today's runs and tasks add up to this."
        )
        for name in TOOLS:
            self.fields[_tool_cost_field(name)] = forms.DecimalField(
                label=f"{name} $ per call",
                min_value=0,
                decimal_places=4,
                initial=self.instance.tool_cost(name),
            )
        _style(self)

    def save(self, commit=True):
        self.instance.tool_costs = {
            **self.instance.tool_costs,
            **{name: str(self.cleaned_data[_tool_cost_field(name)]) for name in TOOLS},
        }
        return super().save(commit)


class LeadFilterForm(forms.Form):
    kind = forms.ChoiceField(choices=[("", "All kinds")] + Lead.Kind.choices, required=False)
    review_status = forms.ChoiceField(choices=[("", "Any review")] + Lead.ReviewStatus.choices, required=False)
    source = forms.ChoiceField(choices=[("", "Any source")] + Lead.Source.choices, required=False)
    stage = forms.ChoiceField(required=False)
    q = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stage"].choices = [("", "Any stage")] + stage_choices()


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
