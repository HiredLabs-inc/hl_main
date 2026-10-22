from .base import AgentType, normalize


class FundingAgent(AgentType):
    key = "funding"
    label = "Funding opportunities"
    lead_kind = "funding"
    fields = {
        "org_name": "org_name",
        "funding_amount": "funding_amount",
        "application_deadline": "application_deadline",
        "application_url": "url",
        "justification": "justification",
    }

    def dedupe_key(self, candidate):
        return normalize(candidate.get("org_name"))
