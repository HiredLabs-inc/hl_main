from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .base import AgentType, normalize


class OutreachAgent(AgentType):
    key = "outreach"
    label = "Outreach partners"
    lead_kind = "outreach"
    fields = {
        "first_name": "first_name",
        "last_name": "last_name",
        "org_name": "org_name",
        "contact_email": "contact_email",
        "justification": "justification",
    }

    def dedupe_key(self, candidate):
        email = normalize(candidate.get("contact_email"))
        try:
            validate_email(email)
        except ValidationError:
            return ""
        return email

    def to_lead(self, candidate):
        values = super().to_lead(candidate)
        values["contact_email"] = self.dedupe_key(candidate)
        return values
