from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .base import SHARED_MAILBOX, AgentType, normalize

# Local parts of addresses that reach an office, not a person
SHARED_MAILBOXES = {
    "admin", "contact", "donate", "donations", "help", "hello", "info", "inquiries", "media", "noreply",
    "no-reply", "office", "outreach", "press", "support", "team", "veterans", "vso", "webmaster",
}


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
    grounded_field = "contact_email"

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

    def validate(self, candidate, sources):
        if self.dedupe_key(candidate).split("@")[0] in SHARED_MAILBOXES:
            return SHARED_MAILBOX
        return super().validate(candidate, sources)
