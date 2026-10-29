"""Reads a page by fetching it directly (docs/designs/in-progress/gcp-agents.md §3.4)."""
import io
import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .base import Tool, ToolError

logger = logging.getLogger(__name__)

# Characters of the page the model sees
PAGE_LENGTH = 12000
# Bytes of the page that are downloaded
MAX_BYTES = 3_000_000
TIMEOUT = 20
MAX_REDIRECTS = 5
# Many sites refuse requests that don't look like a browser's
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
HTML_TYPES = ("text/html", "application/xhtml+xml")
# Tags with no readable text
DROPPED_TAGS = ("script", "style", "noscript", "template", "svg", "iframe")
# Tags that start a new line. Inline ones, like a link inside a sentence, don't.
BLOCK_TAGS = (
    "address", "article", "aside", "blockquote", "dd", "div", "dl", "dt", "figcaption", "footer", "form", "h1", "h2",
    "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table", "td", "th",
    "title", "tr", "ul",
)


def check_url(url):
    """Refuse a URL that isn't http(s) on a public address. The model picks the
    URL, and the worker runs beside the metadata server and other internal
    services."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ToolError(f"{url} isn't an http or https URL.")
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)}
    except (socket.gaierror, UnicodeError):
        raise ToolError(f"Couldn't find {parts.hostname}.") from None
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise ToolError(f"{parts.hostname} isn't a public address.")


def fetch(url):
    """The final URL and response, following redirects by hand so every hop is
    checked."""
    for _ in range(MAX_REDIRECTS + 1):
        check_url(url)
        try:
            response = requests.get(
                url, headers={"User-Agent": USER_AGENT}, allow_redirects=False, stream=True, timeout=TIMEOUT
            )
        except requests.RequestException as e:
            raise ToolError(f"Couldn't read {url}: {e.__class__.__name__}") from e
        if not response.is_redirect:
            return url, response
        response.close()
        url = urljoin(url, response.headers["Location"])
    raise ToolError(f"Couldn't read {url}: too many redirects")


def read_body(response):
    body = b""
    for chunk in response.iter_content(65536):
        body += chunk
        if len(body) >= MAX_BYTES:
            break
    response.close()
    return body[:MAX_BYTES]


def html_text(html, url, encoding=None):
    """The page's text, with each link written as "text (url)" so the lead
    checks can find the URLs and emails it links to."""
    soup = BeautifulSoup(html, "html.parser", from_encoding=encoding)
    for tag in soup(DROPPED_TAGS):
        tag.decompose()
    for link in soup.find_all("a", href=True):
        href = urljoin(url, link["href"].strip())
        if href.startswith(("http://", "https://", "mailto:")):
            text = link.get_text(" ", strip=True)
            # Spaced, so a link with no text can't run into the next one's
            link.replace_with(f" {text} ({href}) " if text and text != href else f" {href} ")
    for tag in soup.find_all("br"):
        tag.replace_with("\n")
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    lines = (" ".join(line.split()) for line in soup.get_text().splitlines())
    return "\n".join(line for line in lines if line)


def pdf_text(body):
    """A PDF's text, page by page, until there's more than the model sees."""
    try:
        reader = PdfReader(io.BytesIO(body))
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
            if len(text) > PAGE_LENGTH:
                break
    except Exception as e:
        # pypdf raises many kinds of errors on broken or cut-off files
        logger.info("Couldn't read a PDF: %s", e)
        raise ToolError(f"Couldn't read the PDF ({e.__class__.__name__}).") from e
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def read_page(url: str) -> dict:
    url, response = fetch(url.strip())
    if response.status_code >= 400:
        response.close()
        raise ToolError(f"Couldn't read {url}: HTTP {response.status_code}")
    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if content_type in HTML_TYPES:
        # The header's charset, if it has one; otherwise the page's own
        encoding = response.encoding if "charset" in response.headers.get("Content-Type", "").lower() else None
        content = html_text(read_body(response), url, encoding)
    elif content_type == "text/plain":
        content = read_body(response).decode(response.encoding or "utf-8", errors="replace")
    elif content_type == "application/pdf":
        content = pdf_text(read_body(response))
    else:
        response.close()
        raise ToolError(f"Can't read {content_type or 'unknown'} pages.")
    return {
        "url": url,
        "content": content[:PAGE_LENGTH],
        "truncated": len(content) > PAGE_LENGTH,
    }


READ_PAGE = Tool(
    name="read_page",
    description=(
        "Read a web page's or PDF's text, with its links and email addresses, to check details a search snippet "
        "doesn't show."
    ),
    parameters={
        "type": "object",
        "properties": {"url": {"type": "string", "description": "The page's full URL"}},
        "required": ["url"],
    },
    func=read_page,
)
