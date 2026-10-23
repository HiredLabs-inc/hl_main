import json
import re
from urllib.parse import urlsplit


class ParseError(ValueError):
    pass


# Reasons a candidate isn't saved. CORRECTABLE ones are sent back to the agent to fix
INCOMPLETE = "incomplete"
DUPLICATE = "already known"
NOT_IN_SOURCES = "not in sources"
HOME_PAGE = "home page"
SHARED_MAILBOX = "shared mailbox"
LISTING_OR_NEWS = "listing or news site"
CORRECTABLE = (NOT_IN_SOURCES, HOME_PAGE, SHARED_MAILBOX, LISTING_OR_NEWS)

URL_PATTERN = re.compile(r"https?://[^\s\"'<>()\[\]\\]+")


class AgentType:
    key = ""
    label = ""
    lead_kind = ""
    allowed_tools = ("web_search", "read_page")
    # {candidate key: Lead field}
    fields = {}
    # The candidate key whose value must appear in what the tools returned
    grounded_field = ""

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

    def validate(self, candidate, sources) -> str:
        """Why the candidate shouldn't be saved, or "". `sources` is the text the
        run's tools returned (conversation.tool_text): a candidate whose
        grounded field isn't in it was made up."""
        if self.grounded_field and not self.in_sources(str(candidate.get(self.grounded_field) or ""), sources):
            return NOT_IN_SOURCES
        return ""

    def in_sources(self, value, sources) -> bool:
        return bool(value) and value.strip().lower() in sources.lower()

    def to_lead(self, candidate) -> dict:
        """Lead field values for a candidate."""
        values = {}
        for key, field in self.fields.items():
            value = candidate.get(key)
            values[field] = "" if value is None else str(value).strip()
        return values


def normalize(text) -> str:
    return " ".join(str(text or "").split()).lower()


def normalize_url(url) -> str:
    """A URL without its scheme, www., query, fragment or trailing slash, so
    two spellings of one page compare equal."""
    parts = urlsplit(str(url or "").strip())
    host = parts.netloc.lower().removeprefix("www.")
    return f"{host}{parts.path.rstrip('/')}" if host else ""
