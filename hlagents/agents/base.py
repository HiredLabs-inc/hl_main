import json
import re


class ParseError(ValueError):
    pass


class AgentType:
    key = ""
    label = ""
    lead_kind = ""
    allowed_tools = ("web_search",)
    # {candidate key: Lead field}
    fields = {}

    def parse(self, text) -> list[dict]:
        """Candidates from the agent's final reply: a JSON list, possibly in a code fence."""
        match = re.search(r"```(?:json)?\s*(.*?)```", text or "", re.DOTALL)
        cleaned = (match.group(1) if match else text or "").strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ParseError(f"The reply isn't valid JSON: {e}") from e

        # Some models wrap the list, e.g. {"candidates": [...]}
        if isinstance(data, dict) and len(data) == 1 and isinstance(next(iter(data.values())), list):
            data = next(iter(data.values()))
        if not isinstance(data, list) or not all(isinstance(c, dict) for c in data):
            raise ParseError("The reply isn't a JSON list of objects.")
        return data

    def dedupe_key(self, candidate) -> str:
        """The normalized key leads are deduped on, or "" to skip the candidate."""
        raise NotImplementedError

    def to_lead(self, candidate) -> dict:
        """Lead field values for a candidate."""
        values = {}
        for key, field in self.fields.items():
            value = candidate.get(key)
            values[field] = "" if value is None else str(value).strip()
        return values


def normalize(text) -> str:
    return " ".join(str(text or "").split()).lower()
