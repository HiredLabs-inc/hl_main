from urllib.parse import urlsplit

from .base import HOME_PAGE, LISTING_OR_NEWS, URL_PATTERN, AgentType, normalize, normalize_url

# Sites that list or write about other funders' grants. A lead's URL has to be
# the funder's own page. Subdomains are blocked too.
BLOCKED_DOMAINS = {
    # Grant listings and directories
    "candid.org", "causeiq.com", "foundationcenter.org", "fundsforngos.org", "grantadvisor.org",
    "grantforward.com", "grantgopher.com", "grantsmarts.com", "grantsoffice.com", "grantspace.org",
    "grantstation.com", "grantwatch.com", "guidestar.org", "insidephilanthropy.com", "instrumentl.com",
    "philanthropynewsdigest.org", "propublica.org", "stemgrants.com",
    # News, press releases and social media
    "accesswire.com", "apnews.com", "businesswire.com", "facebook.com", "forbes.com", "globenewswire.com",
    "linkedin.com", "medium.com", "msn.com", "newswire.com", "nytimes.com", "patch.com", "prnewswire.com",
    "prweb.com", "reuters.com", "washingtonpost.com", "wikipedia.org", "yahoo.com", "youtube.com",
}
# A funder's own news pages: hosts like newsroom.example.com, paths like /news/...
NEWS_HOST_PREFIXES = ("news.", "newsroom.", "press.", "blog.")
NEWS_PATH_SEGMENTS = {"news", "newsroom", "press", "press-release", "press-releases", "blog", "stories"}


def is_listing_or_news(url) -> bool:
    parts = urlsplit(str(url or "").strip())
    host = parts.netloc.lower().split(":")[0].removeprefix("www.")
    if any(host == domain or host.endswith(f".{domain}") for domain in BLOCKED_DOMAINS):
        return True
    if host.startswith(NEWS_HOST_PREFIXES):
        return True
    return bool(NEWS_PATH_SEGMENTS & set(parts.path.lower().split("/")))


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
    grounded_field = "application_url"

    def dedupe_key(self, candidate):
        return normalize(candidate.get("org_name"))

    def validate(self, candidate, sources):
        url = candidate.get("application_url")
        if urlsplit(str(url or "").strip()).path in ("", "/"):
            return HOME_PAGE
        if is_listing_or_news(url):
            return LISTING_OR_NEWS
        return super().validate(candidate, sources)

    def in_sources(self, value, sources):
        url = normalize_url(value)
        return bool(url) and url in {normalize_url(found.rstrip(".,;:")) for found in URL_PATTERN.findall(sources)}
